// Typed client for the Terra backend. Shapes and routes follow docs/api-contract.md.
// This is the only frontend file that names the default API host.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const SESSION_EXPIRED_EVENT = "terra:session-expired";

export type Role = "patient" | "receptionist" | "admin";
export type AppointmentStatus = "booked" | "completed" | "cancelled" | "no_show";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
}

export interface Clinic {
  id: number;
  name: string;
}

export interface Doctor {
  id: number;
  name: string;
  specialty: string;
  bio: string;
  clinic: Clinic;
  next_available: string | null;
}

export interface Slot {
  id: number;
  starts_at: string;
  ends_at: string;
}

export interface Appointment {
  id: number;
  status: AppointmentStatus;
  reason: string;
  patient: { id: number; name: string };
  doctor: { id: number; name: string; specialty: string };
  slot: Slot;
  legacy_schedule: boolean;
}

export interface ActivityItem {
  kind: string;
  text: string;
  at: string;
}

export interface Dashboard {
  user: User;
  next_appointment: Appointment | null;
  counts: { upcoming: number; completed: number; cancelled: number };
  recent_activity: ActivityItem[];
  staff_summary: { today_visits: number; awaiting_outcome: number } | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  return new ApiError(0, "unknown", "Something went wrong. Please try again.");
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed with status ${response.status}.`;
  if (response.status === 422) {
    code = "validation_error";
    message = "Some details were not accepted. Check the form and try again.";
  }
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const d = detail as { code?: unknown; message?: unknown };
      if (typeof d.code === "string") code = d.code;
      if (typeof d.message === "string") message = d.message;
    }
  } catch {
    // Non-JSON error body: keep the status-based defaults above.
  }
  return new ApiError(response.status, code, message);
}

interface RequestInit {
  method?: "GET" | "POST";
  body?: unknown;
  file?: File;
  idempotencyKey?: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const hasBody = init.body !== undefined;
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method ?? "GET",
      credentials: "include",
      cache: "no-store",
      headers: { ...(init.file ? { "Content-Type": "application/octet-stream" } : hasBody ? { "Content-Type": "application/json" } : {}),
        ...(init.idempotencyKey ? { "Idempotency-Key": init.idempotencyKey } : {}) },
      body: init.file ?? (hasBody ? JSON.stringify(init.body) : undefined),
    });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Could not reach the clinic service. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/") && typeof window !== "undefined") {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    throw await errorFromResponse(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const getMe = () => request<User>("/api/auth/me");

export const login = (email: string, password: string) =>
  request<User>("/api/auth/login", { method: "POST", body: { email, password } });

export const logout = () => request<void>("/api/auth/logout", { method: "POST" });

export const getDashboard = () => request<Dashboard>("/api/dashboard");

export const getDoctors = () => request<Doctor[]>("/api/doctors");

export const getDoctorSlots = (doctorId: number, days = 14) =>
  request<Slot[]>(`/api/doctors/${doctorId}/slots?days=${days}`);

export const listAppointments = () => request<Appointment[]>("/api/appointments");

export const bookAppointment = (input: { slot_id: number; reason: string; patient_id?: number }, key?: string) =>
  request<Appointment>("/api/appointments", { method: "POST", body: input, idempotencyKey: key });

export const getPatients = () => request<{ id: number; name: string }[]>("/api/appointments/patients");
export const recordOutcome = (id: number, status: "completed" | "no_show") =>
  request<Appointment>(`/api/appointments/${id}/outcome`, { method: "POST", body: { status } });

export const rescheduleAppointment = (appointmentId: number, slotId: number) =>
  request<Appointment>(`/api/appointments/${appointmentId}/reschedule`, {
    method: "POST",
    body: { slot_id: slotId },
  });

export const cancelAppointment = (appointmentId: number) =>
  request<Appointment>(`/api/appointments/${appointmentId}/cancel`, { method: "POST" });

export interface Guide {
  slug: string;
  title: string;
  body: string;
}

export const getGuides = () => request<Pick<Guide, "slug" | "title">[]>("/api/guides");

export const getGuide = (slug: string) =>
  request<Guide>(`/api/guides/${encodeURIComponent(slug)}`);

export interface PatientDocument { slug: string; title: string; pages: number; patient_case_id?: string | null }
export interface DocumentTurn { role: "user" | "assistant"; text: string }
export interface DocumentReply {
  reply: string; citations: AssistantCitation[]; ai_notice: string | null; origin: string;
}
const patientQuery = (patientId?: number) => patientId === undefined ? "" : `?patient_id=${patientId}`;
export const getPatientDocuments = (patientId?: number) => request<PatientDocument[]>(`/api/patient-documents${patientQuery(patientId)}`);
export const uploadPatientDocument = (file: File) => request<PatientDocument>(
  `/api/patient-documents/upload?filename=${encodeURIComponent(file.name)}`, { method: "POST", file },
);
export const getPatientDocument = (slug: string, patientId?: number) =>
  request<Guide>(`/api/patient-documents/${encodeURIComponent(slug)}${patientQuery(patientId)}`);
export interface PatientSummary {
  patient: { id: number; name: string; email: string | null };
  appointments: Appointment[];
  access: "full" | "current_shared";
}
export const getPatientSummary = (patientId?: number) =>
  request<PatientSummary>(`/api/patient-documents/summary${patientQuery(patientId)}`);
export const askPatientDocument = (question: string, document_id: string | null, history: DocumentTurn[]) =>
  request<DocumentReply>("/api/patient-documents/chat", { method: "POST", body: { question, document_id, history } });

export async function getPatientPdf(slug: string, signal: AbortSignal, patientId?: number): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/patient-documents/${encodeURIComponent(slug)}/pdf${patientQuery(patientId)}`,
    { credentials: "include", cache: "no-store", signal });
  if (!response.ok) throw await errorFromResponse(response);
  return response.blob();
}

export interface AssistantCitation {
  slug: string;
  title: string;
  scope?: "guide" | "patient" | "insights";
  patient_id?: number | null;
}

export type AssistantActionType = "book" | "cancel" | "reschedule";

export interface AssistantProposedAction {
  id: number;
  type: AssistantActionType;
  summary: string;
  params: Record<string, unknown>;
}

export interface AssistantReply {
  reply: string;
  citations: AssistantCitation[];
  proposed_action: AssistantProposedAction | null;
  ai_notice?: string | null;
  origin?: string | null;
}

export const sendAssistantMessage = (message: string, patientId?: number, workspace?: {
  context: "auto" | "documents" | "insights"; document_id: string | null; history: DocumentTurn[];
}) =>
  request<AssistantReply>("/api/assistant/message", { method: "POST", body: {
    message, patient_id: patientId, ...(workspace ? { workspace: true, ...workspace } : {}),
  } });

export const confirmAssistantAction = (actionId: number) =>
  request<{ status: "confirmed"; appointment: Appointment }>(
    `/api/assistant/actions/${actionId}/confirm`,
    { method: "POST" },
  );

export const dismissAssistantAction = (actionId: number) =>
  request<{ status: "dismissed" }>(`/api/assistant/actions/${actionId}/dismiss`, {
    method: "POST",
  });

export interface InsightsTotals {
  booked: number;
  completed: number;
  cancelled: number;
  no_show: number;
  cancellation_rate: number;
  no_show_rate: number;
}

export interface InsightsHistoryDay {
  day: string;
  booked: number;
  completed: number;
  cancelled: number;
  no_show: number;
  capacity: number;
  data_status: "observed" | "no_schedule";
}

export interface InsightsForecastPoint {
  day: string;
  predicted_booked: number | null;
  confirmed: number;
  capacity: number;
  remaining_capacity: number | null;
  utilisation: number | null;
  schedule_status: "published" | "no_schedule";
  estimate_status: "ready" | "insufficient_history" | "no_schedule";
}

export interface DemandMetrics {
  mae: number;
  rmse: number;
  samples: number;
  mae_by_horizon: number[];
  negative_raw: number;
  above_capacity_raw: number;
  open_day_predictions: number;
  mae_open_days: number | null;
}

export type WorkloadForecastData = { status: "unavailable" | "stale"; message: string } | {
  status: "ready";
  source: string;
  selected_method: "linear_regression" | "baseline";
  trained_at: string;
  training_start: string;
  training_end: string;
  training_days: number;
  dataset_id: string;
  features: string[];
  versions: Record<string, string>;
  comparisons: { scenario: string; selected_method: string; holdout: Record<"linear_regression" | "baseline", DemandMetrics> }[];
  history: { day: string; demand: number }[];
  points: { day: string; predicted_booked: number; linear_regression: number; baseline: number; capacity: number }[];
  metrics: {
    validation: Record<"linear_regression" | "baseline", DemandMetrics>;
    holdout: Record<"linear_regression" | "baseline", DemandMetrics>;
    selection_basis: string;
    holdout_start: string;
    holdout_end: string;
    protocol: string;
  };
};

export interface Insights {
  totals: InsightsTotals;
  window_days: number;
  history: InsightsHistoryDay[];
  source: string;
  timezone: string;
  history_note: string;
  business: {
    expected_visits: number | null;
    confirmed_visits: number;
    capacity: number;
    published_days: number;
    utilisation: number | null;
    remaining_capacity: number | null;
  };
  model_demo: WorkloadForecastData;
  forecast: {
    label: string;
    method: string;
    points: InsightsForecastPoint[];
    status: "limited_history" | "baseline";
    message: string;
    observed_days: number;
    history_span_days: number;
  };
}

export const getInsights = () => request<Insights>("/api/insights");

export interface CountEvaluation {
  uncertainty?: { level: number; draws: number; seed: number; block_days: number; method: string; coefficient_intervals: number[][]; mean_intervals: number[][]; prediction_intervals: number[][]; monthly_prediction_interval: number[] };
  selected_method: string;
  forecast_month: string;
  forecast_total: number;
  holdout_month: string;
  metrics: Record<string, Record<string, { daily_mae: number; rmse: number; r2: number; predicted_total: number; actual_total: number }>>;
  model: { intercept: number; coefficients: number[]; features: string[]; training_days: number; training_start: string; training_end: string; design_rank: number; design_columns: number; training_rmse_raw: number };
  points: { day: string; predicted: number; regression: number; baseline: number; capacity: number; features: number[]; raw: number }[];
  evaluation_points: Record<string, { day: string; actual: number; linear_regression: number; weekday_baseline: number }[]>;
}
export interface ClassifierEvaluation {
  month: string; samples: number; no_shows: number; logistic_brier: number; baseline_brier: number; roc_auc: number | null;
  average_precision: number; precision_at_half: number; recall_at_half: number; f1_at_half: number; confusion_matrix: number[][];
  roc: { x: number; y: number; threshold: number | null }[];
  precision_recall: { x: number; y: number }[];
  calibration: { predicted: number; observed: number; count: number }[];
  model: { intercept: number; coefficients: number[]; mean: number[]; scale: number[]; training_samples: number; features: string[] };
}
export interface CsvEvaluation {
  source: string;
  validation: { appointments: number; patients: number };
  busyness: CountEvaluation;
  no_show_counts: CountEvaluation;
  individual_no_shows: {
    selected_method: string;
    metrics: Record<string, ClassifierEvaluation>;
  };
  retention: { message: string };
}
export const getCsvEvaluation = () => request<CsvEvaluation>("/api/insights/csv-evaluation");
export interface ForecastReplay {
  forecast_origin: string; known_through: string;
  points: { day: string; actual: number; regression: number; baseline: number; capacity: number }[];
  mae_all_days: { regression: number; baseline: number };
  mae_open_days: { regression: number | null; baseline: number | null };
}
export const replayForecast = (origin: string) => request<ForecastReplay>(`/api/insights/replay?origin=${encodeURIComponent(origin)}`);

interface ReturnMetrics {
  samples: number; brier: number; roc_auc: number; average_precision: number;
  precision_at_half: number; recall_at_half: number; return_rate: number;
  calibration: { range: number[]; count: number; predicted: number; observed: number }[];
}
export interface Retention {
  notice: string;
  patients: { id: number; name: string; return_probability: number | null; days_since_completed: number | null;
    last_completed: string | null; completed_visits: number; next_booking: string | null; open_task: number | null;
    review_eligible: boolean; reason: string }[];
  tasks: { id: number; patient_id: number; patient_name: string; note: string; status: string; outcome: string;
    created_at: string; completed_at: string | null; subsequent_return: boolean }[];
  model: null | { selected_method: string; trained_at: string; training_samples: number; population: number;
    training_label_end: string; validation_origin: string; holdout_origin: string;
    metrics: { validation: { logistic: ReturnMetrics; baseline: ReturnMetrics }; holdout: { logistic: ReturnMetrics; baseline: ReturnMetrics } };
    examples: { name: string; features: number[]; probability: number }[] };
}
export const getRetention = () => request<Retention>("/api/retention");
export const createFollowUp = (patientId: number, note: string) => request<{ id: number }>("/api/retention/tasks", { method: "POST", body: { patient_id: patientId, note } });
export const completeFollowUp = (id: number, outcome: string) => request<{ id: number }>(`/api/retention/tasks/${id}/complete`, { method: "POST", body: { outcome } });
