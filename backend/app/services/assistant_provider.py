"""Assistant provider interface and the local rule-based provider.

A provider reads a plain AssistantContext and returns a ProviderResult. It never touches the
database and never executes anything: a proposed action is only stored as `pending` by
app.services.assistant, and only an explicit confirm runs it.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from app.clinic import format_when

REFUSAL = "I can only help with Terra Family Clinic information and your appointments."

CANCEL_WORDS = {"cancel", "cancelling"}
RESCHEDULE_WORDS = {"reschedule", "rescheduling", "move", "change"}
BOOK_WORDS = {"book", "schedule"}
UPCOMING_PHRASES = ("my appointments", "next appointment")
UPCOMING_WORDS = {"upcoming"}

# Words added to the message before guide scoring.
SYNONYMS: dict[str, list[str]] = {
    "hours": ["opening"],
    "open": ["opening"],
    "closing": ["opening"],
    "where": ["parking", "directions"],
    "address": ["parking", "directions"],
    "directions": ["parking", "directions"],
    "parking": ["parking", "directions"],
    "documents": ["bring"],
    "privacy": ["privacy"],
    "data": ["privacy"],
    "late": ["cancellation"],
    "fee": ["cancellation"],
    "book": ["booking"],
    "booking": ["booking"],
}

STOPWORDS = {
    "about", "also", "and", "any", "are", "can", "could", "does", "for", "from", "get", "have", "how",
    "into", "just", "need", "not", "out", "please", "should", "some", "tell", "that", "the", "their",
    "there", "this", "what", "when", "which", "who", "will", "with", "would", "you", "your", "want",
    "policy", "policies",
}

MAX_UPCOMING_LISTED = 3


@dataclass(frozen=True)
class GuideRef:
    slug: str
    title: str
    body: str


@dataclass(frozen=True)
class DoctorRef:
    id: int
    name: str
    specialty: str


@dataclass(frozen=True)
class AppointmentRef:
    id: int
    slot_id: int
    doctor_id: int
    doctor_name: str
    specialty: str
    starts_at: datetime


@dataclass(frozen=True)
class FreeSlot:
    id: int
    doctor_id: int
    starts_at: datetime


@dataclass
class AssistantContext:
    user_id: int
    guides: list[GuideRef]
    doctors: list[DoctorRef]
    upcoming: list[AppointmentRef]  # the user's booked, future appointments, earliest first
    earliest_free_slot: Callable[[int], FreeSlot | None]
    actor_role: str = "patient"
    patient_name: str = ""


@dataclass
class ProviderResult:
    reply: str
    citations: list[dict[str, str]] = field(default_factory=list)
    proposed_action: dict[str, Any] | None = None


class AssistantProvider(Protocol):
    def reply(self, message: str, context: AssistantContext) -> ProviderResult: ...


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _format_when(dt: datetime) -> str:
    return format_when(dt)


def _doctor_label(name: str, specialty: str) -> str:
    return f"{name} ({specialty})"


def _first_sentences(body: str, count: int) -> str:
    sentences = re.split(r"(?<=\.)\s+", body.strip())
    return " ".join(sentences[:count])


class RuleBasedProvider:
    def reply(self, message: str, context: AssistantContext) -> ProviderResult:
        words = _words(message)
        word_set = set(words)
        text = " ".join(words)

        # Process/policy questions explain a guide; they do not request a visit change.
        if word_set & {"policy", "policies", "rules", "procedure", "process", "explain"} or text.startswith(
            ("how ", "what happens ", "what if ")
        ):
            return self._guide(words, context)
        if word_set & CANCEL_WORDS:
            return self._cancel(context)
        if word_set & RESCHEDULE_WORDS:
            return self._reschedule(context)
        if self._wants_booking(word_set, text):
            if word_set & {"today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"} or re.search(r"\d", message):
                return ProviderResult(reply="Do you want the earliest available time instead? For a specific date, please use Doctors and its date picker. No appointment has been selected.")
            booked = self._book(word_set, context)
            if booked is not None:
                return booked
        if any(phrase in text for phrase in UPCOMING_PHRASES) or word_set & UPCOMING_WORDS:
            return self._upcoming(context)
        return self._guide(words, context)

    # --- appointment intents ------------------------------------------------------

    def _cancel(self, context: AssistantContext) -> ProviderResult:
        if not context.upcoming:
            return ProviderResult(reply="You have no upcoming appointments to cancel.")
        target = context.upcoming[0]
        summary = f"Cancel your appointment with {target.doctor_name} on {_format_when(target.starts_at)}"
        return ProviderResult(
            reply="I can cancel your next appointment. Confirm to cancel it.",
            proposed_action={"type": "cancel", "params": {"appointment_id": target.id}, "summary": summary},
        )

    def _reschedule(self, context: AssistantContext) -> ProviderResult:
        if not context.upcoming:
            return ProviderResult(reply="You have no upcoming appointments to reschedule.")
        current = context.upcoming[0]
        free = context.earliest_free_slot(current.doctor_id)
        if free is None:
            return ProviderResult(
                reply=f"There is no free slot with {current.doctor_name} right now, so there is nothing to move to."
            )
        summary = (
            f"Move your appointment with {current.doctor_name} from {_format_when(current.starts_at)} "
            f"to {_format_when(free.starts_at)}"
        )
        return ProviderResult(
            reply="I can move your next appointment to the earliest free slot with the same doctor. Confirm to move it.",
            proposed_action={
                "type": "reschedule",
                "params": {"appointment_id": current.id, "slot_id": free.id},
                "summary": summary,
            },
        )

    def _wants_booking(self, word_set: set[str], text: str) -> bool:
        return bool(word_set & BOOK_WORDS) or "appointment with" in text

    def _book(self, word_set: set[str], context: AssistantContext) -> ProviderResult | None:
        doctor = self._match_doctor(word_set, context)
        if doctor is None:
            return ProviderResult(reply="Which doctor or specialty would you like? Please name one doctor or choose Family Medicine, Pediatrics, Dermatology, Cardiology, Physiotherapy, or Women's Health.")
        free = context.earliest_free_slot(doctor.id)
        if free is None:
            return ProviderResult(reply=f"There is no free slot with {doctor.name} in the next two weeks.")
        summary = f"Book {_doctor_label(doctor.name, doctor.specialty)} on {_format_when(free.starts_at)}"
        return ProviderResult(
            reply=f"I can book the earliest free slot with {doctor.name}. Confirm to book it.",
            proposed_action={
                "type": "book",
                "params": {"slot_id": free.id, "reason": "Booked via assistant",
                           **({"patient_id": context.user_id} if context.actor_role != "patient" else {})},
                "summary": summary,
            },
        )

    def _match_doctor(self, word_set: set[str], context: AssistantContext) -> DoctorRef | None:
        aliases = {"family medicine": {"general", "gp", "family"}, "pediatrics": {"pediatrician", "paediatrician", "pediatrics", "children"},
                   "dermatology": {"dermatologist", "dermatology", "skin"}, "cardiology": {"cardiologist", "cardiology", "heart"},
                   "physiotherapy": {"physiotherapist", "physiotherapy", "physio"}, "women's health": {"gynecologist", "gynaecologist"}}
        named = []
        matched = []
        for doctor in context.doctors:
            name_words = [w for w in _words(doctor.name) if w != "dr" and len(w) >= 3]
            if any(w in word_set for w in name_words):
                named.append(doctor)
            specialty_words = set(_words(doctor.specialty))
            if specialty_words <= word_set or aliases.get(doctor.specialty.lower(), set()) & word_set:
                matched.append(doctor)
        candidates = named if named else matched
        return candidates[0] if len(candidates) == 1 else None

    def _upcoming(self, context: AssistantContext) -> ProviderResult:
        if not context.upcoming:
            return ProviderResult(reply="You have no upcoming appointments.")
        lines = [
            f"- {a.doctor_name} ({a.specialty}) on {_format_when(a.starts_at)}"
            for a in context.upcoming[:MAX_UPCOMING_LISTED]
        ]
        return ProviderResult(reply="Your upcoming appointments:\n" + "\n".join(lines))

    # --- guide lookup -----------------------------------------------------------------

    def _guide(self, words: list[str], context: AssistantContext) -> ProviderResult:
        query: set[str] = set()
        for word in words:
            query.add(word)
            query.update(SYNONYMS.get(word, []))
        query = {w for w in query if len(w) >= 4 and w not in STOPWORDS}

        best: GuideRef | None = None
        best_score = 0
        for guide in context.guides:
            guide_words = {w for w in _words(guide.title + " " + guide.body) if len(w) >= 4}
            score = len(query & guide_words)
            if score > best_score:
                best, best_score = guide, score
        if best is None:
            return ProviderResult(reply=REFUSAL)
        return ProviderResult(
            reply=_first_sentences(best.body, 2),
            citations=[{"slug": best.slug, "title": best.title}],
        )
