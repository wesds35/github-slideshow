// Hand-written to match supabase/schema.sql. If you later run the Supabase CLI's type generator
// (`supabase gen types typescript`), its output can replace this file directly — the shape here
// is deliberately structured the same way (including the `Relationships` field each table needs,
// even though we leave it empty since we never rely on typed embedded-resource joins) so nothing
// else needs to change.

export type VolumeTrack = "load" | "distance" | "wattage";
export type SessionStatus = "scheduled" | "completed" | "missed";
export type Role = "coach" | "athlete";

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: { id: string; role: Role; full_name: string | null; created_at: string };
        Insert: { id: string; role?: Role; full_name?: string | null };
        Update: { role?: Role; full_name?: string | null };
        Relationships: [];
      };
      athletes: {
        Row: {
          id: string;
          user_id: string | null;
          name: string;
          initials: string;
          email: string;
          created_at: string;
        };
        Insert: { id?: string; user_id?: string | null; name: string; initials: string; email: string };
        Update: { user_id?: string | null; name?: string; initials?: string; email?: string };
        Relationships: [];
      };
      programs: {
        Row: { id: string; name: string; duration_weeks: number; tags: string; created_at: string };
        Insert: { id?: string; name: string; duration_weeks: number; tags?: string };
        Update: { name?: string; duration_weeks?: number; tags?: string };
        Relationships: [];
      };
      program_weeks: {
        Row: { id: string; program_id: string; week_number: number };
        Insert: { id?: string; program_id: string; week_number: number };
        Update: { week_number?: number };
        Relationships: [];
      };
      program_days: {
        Row: { id: string; program_id: string; week_id: string; label: string; order: number };
        Insert: { id?: string; program_id: string; week_id: string; label: string; order: number };
        Update: { label?: string; order?: number };
        Relationships: [];
      };
      program_exercises: {
        Row: {
          id: string;
          program_id: string;
          day_id: string;
          name: string;
          track: VolumeTrack;
          prescribed_sets: number;
          prescribed_reps: number | null;
          prescription_note: string;
          rest_note: string;
          order: number;
        };
        Insert: {
          id?: string;
          program_id: string;
          day_id: string;
          name: string;
          track: VolumeTrack;
          prescribed_sets: number;
          prescribed_reps?: number | null;
          prescription_note?: string;
          rest_note?: string;
          order: number;
        };
        Update: {
          name?: string;
          track?: VolumeTrack;
          prescribed_sets?: number;
          prescribed_reps?: number | null;
          prescription_note?: string;
          rest_note?: string;
          order?: number;
        };
        Relationships: [];
      };
      assignments: {
        Row: { id: string; program_id: string; athlete_id: string; start_date: string; created_at: string };
        Insert: { id?: string; program_id: string; athlete_id: string; start_date: string };
        Update: Record<string, never>;
        Relationships: [];
      };
      scheduled_sessions: {
        Row: {
          id: string;
          assignment_id: string;
          athlete_id: string;
          day_id: string;
          date: string;
          status: SessionStatus;
        };
        Insert: {
          id?: string;
          assignment_id: string;
          athlete_id: string;
          day_id: string;
          date: string;
          status?: SessionStatus;
        };
        Update: { status?: SessionStatus };
        Relationships: [];
      };
      logged_sets: {
        Row: {
          id: string;
          session_id: string;
          exercise_id: string;
          athlete_id: string;
          exercise_name: string;
          track: VolumeTrack;
          set_number: number;
          weight: number | null;
          reps: number | null;
          distance: number | null;
          load: number | null;
          watts: number | null;
          duration_sec: number | null;
          volume: number;
          is_pr: boolean;
          logged_at: string;
        };
        Insert: {
          id?: string;
          session_id: string;
          exercise_id: string;
          athlete_id: string;
          exercise_name: string;
          track: VolumeTrack;
          set_number: number;
          weight?: number | null;
          reps?: number | null;
          distance?: number | null;
          load?: number | null;
          watts?: number | null;
          duration_sec?: number | null;
          volume: number;
          is_pr?: boolean;
          logged_at?: string;
        };
        Update: Record<string, never>;
        Relationships: [];
      };
      badge_definitions: {
        Row: { id: string; track: VolumeTrack; tier: number; name: string; threshold: number };
        Insert: { id: string; track: VolumeTrack; tier: number; name: string; threshold: number };
        Update: { threshold?: number };
        Relationships: [];
      };
      earned_badges: {
        Row: { id: string; athlete_id: string; badge_definition_id: string; earned_at: string };
        Insert: { id?: string; athlete_id: string; badge_definition_id: string; earned_at?: string };
        Update: Record<string, never>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
  };
}
