export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  video_count: number;
  clip_count: number;
}

export interface VideoMetadata {
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  video_codec: string | null;
  audio_codec: string | null;
  aspect_ratio: string | null;
  bitrate: number | null;
  file_size_bytes: number;
  format_name: string | null;
  video_stream_count: number;
  audio_stream_count: number;
  raw?: Record<string, unknown> | null;
}

export interface SourceVideo {
  id: string;
  project_id: string;
  original_filename: string;
  stored_path: string;
  file_size_bytes: number;
  content_type: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  video_codec: string | null;
  audio_codec: string | null;
  aspect_ratio: string | null;
  bitrate: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  metadata?: VideoMetadata | null;
}

export interface VideoImportResponse {
  project: { id: string; name: string; status: string };
  video: SourceVideo;
  message: string;
}

export interface ProcessingJob {
  id: string;
  project_id: string | null;
  video_id: string | null;
  clip_id: string | null;
  job_type: string;
  status: string;
  current_stage: string | null;
  progress: number;
  message: string | null;
  error: string | null;
  stages_json?: Array<Record<string, unknown>> | null;
  result_json?: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_projects: number;
  imported_videos: number;
  generated_clips: number;
  active_jobs: number;
  recent_projects: Project[];
  recent_jobs: ProcessingJob[];
  hardware: Record<string, unknown>;
}

export interface AppSettings {
  ollama_url: string;
  ollama_model: string;
  whisper_model: string;
  whisper_device: string;
  prefer_gpu: boolean;
  max_concurrent_jobs: number;
  use_nvenc: string;
  ffmpeg_path: string | null;
  ffprobe_path: string | null;
  workspace_path: string;
  output_width: number;
  output_height: number;
  output_fps: number;
  crf: number;
  clip_min_seconds: number;
  clip_max_seconds: number;
  hardware: Record<string, unknown>;
}

export interface TranscriptionWord {
  word: string;
  start: number;
  end: number;
  confidence: number | null;
  index?: number;
}

export interface TranscriptionSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  avg_logprob: number | null;
  no_speech_prob: number | null;
  words: TranscriptionWord[];
}

export interface Transcription {
  id: string;
  video_id: string;
  language: string | null;
  language_probability: number | null;
  model_name: string;
  full_text: string | null;
  audio_path: string | null;
  duration_seconds: number | null;
  created_at: string;
  segment_count: number;
  word_count: number;
  segments?: TranscriptionSegment[] | null;
  words?: TranscriptionWord[] | null;
}

export interface Highlight {
  id: string;
  video_id: string;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  transcript: string | null;
  hook: string | null;
  category: string | null;
  description: string | null;
  score: number;
  score_breakdown?: Record<string, number> | null;
  reason: string | null;
  selected: boolean;
  rank: number | null;
  created_at: string;
}

export interface Clip {
  id: string;
  project_id: string;
  video_id: string;
  highlight_id: string | null;
  title: string | null;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  score: number;
  category: string | null;
  hook: string | null;
  transcript: string | null;
  reframing_mode: string;
  status: string;
  output_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface AudioTrack {
  id: string;
  clip_id: string;
  track_type: string;
  label: string;
  source_path: string | null;
  volume: number;
  muted: boolean;
  start_seconds: number;
  end_seconds: number | null;
  offset_seconds: number;
  fade_in_seconds: number;
  fade_out_seconds: number;
  loop: boolean;
  ducking_enabled: boolean;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface AudioMixSettings {
  enable_loudnorm: boolean;
  enable_limiter: boolean;
  integrated_lufs: number;
  true_peak: number;
  lra: number;
  ducking_threshold: number;
  ducking_ratio: number;
  ducking_attack_ms: number;
  ducking_release_ms: number;
  preset_slug?: string | null;
}

export interface AudioStudioState {
  clip_id: string;
  duration_seconds: number;
  tracks: AudioTrack[];
  mix_settings: AudioMixSettings;
  audio_presets: Array<{ id: string; name: string; slug?: string; config: Record<string, unknown> }>;
}

export interface SubtitlePreset {
  id: string;
  name: string;
  slug: string;
  config: Record<string, unknown>;
  is_builtin: boolean;
}
