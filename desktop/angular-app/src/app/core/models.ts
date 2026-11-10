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
