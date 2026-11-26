"""Reproduce the two synthetic dataset releases under backend/data/synthetic-v1."""

import subprocess
import os
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import simpleSplit

ROOT = Path(__file__).resolve().parents[1] / "backend/data/synthetic-v1"
SEED = 8241

# Each entry pairs an original public-facing guide with evaluation questions.
GUIDES = {
    "clinic-hours": (
        "Opening times and last appointments",
        "Reception opens at 08:00 and closes at 18:00 Monday through Friday. On Saturday the clinic opens at 09:00 and closes at 13:00. Sunday is a closure day.\n\n"
        "Visits occupy half-hour slots. The final weekday slot starts at 17:30. The final Saturday slot starts at 12:30. Opening hours describe the service window. The booking calendar shows which slots are still available.",
        [("When does reception open on Saturday?", "09:00"), ("Can I start a Saturday appointment at one?", "The final Saturday slot starts at 12:30.")]),
    "first-visit": (
        "Preparing for your first visit",
        "Arrive 10 minutes before your first visit so reception can complete check-in. Bring a photo ID and a health card or insurance details. Have your booking reference ready at the desk.\n\n"
        "Bring a list of current medicines. If you already have relevant test results or a referral letter, bring those along. Keep the originals with you until a member of staff asks to see them.",
        [("How early should a new visitor arrive?", "10 minutes"), ("What identification is requested at check-in?", "photo ID")]),
    "change-a-booking": (
        "Moving an upcoming appointment",
        "Open Appointments and select the upcoming booked visit you want to move. Choose a free slot with the same doctor and review the new date and time. Check the appointment details after confirmation.\n\n"
        "A completed visit is part of your past history. To see another specialty, browse Find a doctor and check that clinician's published availability.",
        [("Can I move my visit to another time with my clinician?", "Choose a free slot with the same doctor"), ("Where do I look for another specialty?", "Find a doctor")]),
    "cancellation": (
        "When you cannot attend",
        "Cancellation is free until 24 hours before the appointment starts. If your plans change later, you can still cancel the booking. Please call the front desk so staff can offer the slot to another visitor.\n\n"
        "After cancelling, look in the cancelled appointments list to check the status. Moving a visit to a different available time is handled through rescheduling.",
        [("What is the free cancellation window?", "24 hours"), ("Who should I call for a late cancellation?", "front desk")]),
    "getting-here": (
        "Parking and accessible arrival",
        "The clinic entrance is at 12 Terra Lane. The clinic car park behind the building offers free parking. Street parking is limited to two hours.\n\n"
        "Visitors who need step-free access should use the side entrance. The signed entrance to the car park and the accessible entrance to the building serve different purposes.",
        [("Is there a time restriction for roadside parking?", "two hours"), ("Which doorway has step-free access?", "side entrance")]),
    "floor-directory": (
        "Floor directory and lift labels",
        "Ground floor: The sample collection desk is in room G012 near the east entrance. Reception can help visitors read the floor directory.\n\n"
        "Level 2: The Blue Lift serves this level. The physiotherapy reception is in room B214 across from the Blue Lift. Use the room number when asking reception for directions.",
        [("Where do I check in for physiotherapy?", "room B214"), ("Which room has the sample collection desk?", "room G012")]),
    "demo-privacy": (
        "Privacy and account access",
        "Account sessions expire after 8 hours. Sign out when finished. The shared library contains clinic guides approved for all signed-in users.\n\n"
        "Keep patient records outside the shared library. Patients can access their own records; the owner can review all records. Receptionists can view explicitly shared current notes and prescriptions, not previous medical records.\n\n"
        "Document questions and relevant excerpts may be sent to OpenAI. AI-generated explanations require review. Select a source citation to read the page used for an answer.",
        [("How long does an account session last?", "8 hours"), ("How do I inspect the evidence for a document answer?", "Select a source citation")]),
    "booking-a-visit": (
        "Finding and confirming a slot",
        "In Find a doctor, use the specialty filter and open a doctor's available slots. Select the date and time, then review the booking details. Each scheduled visit lasts 30 minutes.\n\n"
        "An assistant suggestion is a proposal. Review the patient, clinician and time before confirming it. Open Appointments to see the confirmed visit.",
        [("How much calendar time does one visit take?", "30 minutes"), ("What should I review before confirming a suggested booking?", "patient, clinician and time")]),
}


def write_rag():
    folder = ROOT / "rag" / "documents"
    folder.mkdir(parents=True, exist_ok=True)
    examples = []
    for slug, (title, body, questions) in GUIDES.items():
        filename = ("privacy-and-access" if slug == "demo-privacy" else slug) + ".pdf"
        page = Canvas(str(folder / filename), pagesize=(595, 620), invariant=1)
        page.setTitle(title)
        page.setFont("Helvetica-Bold", 11)
        page.setFillColorRGB(.17, .37, .33)
        page.drawString(48, 560, "TERRA FAMILY CLINIC   /   VISITOR GUIDE")
        page.setFont("Times-Bold", 28)
        page.drawString(48, 509, title)
        page.setFillColorRGB(.14, .18, .17)
        page.setFont("Helvetica", 13)
        y = 460
        for paragraph in body.split("\n\n"):
            for line in simpleSplit(paragraph, "Helvetica", 13, 499):
                page.drawString(48, y, line)
                y -= 21
            y -= 18
        assert y > 60
        page.setFont("Helvetica", 10)
        page.drawString(48, 44, "Terra Family Clinic / Patient information")
        page.drawRightString(547, 44, "1 / 1")
        page.save()
        for query, quote in questions:
            assert quote in body
            examples.append(dict(question=query, source=filename, page=1, evidence=quote, answerable=True))
    for query in ("What is the price of an MRI?", "What is the clinic Wi-Fi password?",
                  "Does the car park have an EV charger?", "Which bus route stops at Terra Lane?"):
        examples.append(dict(question=query, source=None, page=None, evidence=None, answerable=False))
    with (folder.parent / "evaluation.jsonl").open("w", encoding="utf-8", newline="\n") as out:
        for example in examples:
            out.write(json.dumps(example, ensure_ascii=False) + "\n")


def write_demand():
    rng = random.Random(SEED)
    folder = ROOT / "linear-regression"
    folder.mkdir(parents=True, exist_ok=True)
    start, end = date(2023, 1, 1), date(2025, 12, 31)
    records = {}
    shock = 0.0
    for i in range((end - start).days + 1):
        day = start + timedelta(days=i)
        weekday = day.weekday()
        closure = weekday == 6 or (day.month, day.day) in {(1, 26), (8, 15), (10, 2)}
        capacity = 0 if closure else (48 if weekday == 5 else 120)
        if capacity and rng.random() < 0.055:
            capacity -= 8  # Synthetic reduced staffing day
        shock = 0.65 * shock + rng.gauss(0, 0.025)
        seasonal = 0.06 * math.cos(2 * math.pi * i / 365.25)
        fill = min(0.96, max(0.35, [0.76, 0.66, 0.62, 0.64, 0.70, 0.78, 0][weekday]
                             + 0.00006 * i + seasonal + shock))
        booked = sum(rng.random() < fill for _ in range(capacity))
        cancelled = sum(rng.random() < 0.075 for _ in range(booked))
        demand = booked - cancelled
        no_show = sum(rng.random() < 0.055 for _ in range(demand))
        recent = [records[day - timedelta(weeks=w)]["demand"] for w in range(1, 5)
                  if day - timedelta(weeks=w) in records]
        split = "train" if day < date(2025, 7, 1) else "validation" if day < date(2025, 10, 1) else "test"
        records[day] = dict(day=day.isoformat(), weekday=weekday, capacity=capacity,
                            demand_lag_7d=recent[0] if recent else None,
                            demand_mean_prior_4_weekdays=sum(recent)/4 if len(recent) == 4 else None,
                            booked=booked, cancelled=cancelled, completed=demand-no_show,
                            no_show=no_show, demand=demand, split=split)
    runtime = Path(os.environ.get("TERRA_ARTIFACT_RUNTIME", Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"))
    node = runtime / "bin" / ("node.exe" if os.name == "nt" else "node")
    subprocess.run([str(node), str(Path(__file__).with_name("write_demand_workbook.mjs")),
                    str(runtime), str(folder / "daily-demand.xlsx")],
                   input=json.dumps(list(records.values())), text=True, check=True)


if __name__ == "__main__":
    write_rag()
    write_demand()
