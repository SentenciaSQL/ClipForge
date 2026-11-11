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
  thumbnail_path?: string | null;
  has_audio?: boolean;
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
  speaker_label?: string | null;
}

export interface TranscriptionSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  avg_logprob: number | null;
  no_speech_prob: number | null;
  speaker_label?: string | null;
  words: TranscriptionWord[];
}

export interface Speaker {
  id: string;
  video_id: string;
  label: string;
  display_name: string | null;
  metadata_json?: Record<string, unknown> | null;
}

export interface WaveformTrack {
  track_id: string;
  track_type: string;
  label: string;
  muted: boolean;
  volume: number;
  ducking_enabled: boolean;
  peaks: number[];
  duration_seconds?: number;
  error?: string;
}

export interface ClipWaveforms {
  clip_id: string;
  duration_seconds: number;
  start_seconds: number;
  end_seconds: number;
  waveforms: WaveformTrack[];
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
  preview_path?: string | null;
  subtitle_preset_id?: string | null;
  render_settings?: Record<string, unknown> | null;
  audio_config?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SubtitleStyleConfig {
  font_family: string;
  font_size: number;
  font_weight: 'normal' | 'bold';
  text_color: string;
  highlight_color: string;
  outline_color: string;
  outline_width: number;
  shadow: number;
  opacity: number;
  alignment: 'left' | 'center' | 'right';
  position: 'top' | 'center' | 'bottom' | 'custom';
  custom_vertical: number;
  margin_h: number;
  max_chars_per_line: number;
  max_lines: number;
  animation: string;
  uppercase: boolean;
  safe_area: 'none' | 'tiktok' | 'reels' | 'shorts';
}

export interface ClipConfiguration {
  schema_version: number;
  subtitles: {
    enabled: boolean;
    preset_slug: string;
    style: SubtitleStyleConfig;
    segments?: { text: string; start: number; end: number }[] | null;
  };
  video: {
    aspect_ratio: string;
    resolution_label: string;
    width: number;
    height: number;
    fps: number | null;
    preserve_source_fps: boolean;
    quality_preset: string;
    crf: number;
    codec: string;
    encoder: string;
  };
  reframe: {
    mode: string;
    background_color: string;
    focal_x: number;
    focal_y: number;
    enable_face_detection: boolean;
    manual_crop?: { x: number; y: number; width: number; height: number } | null;
  };
  audio: {
    codec: string;
    bitrate_kbps: number;
    volume: number;
  };
  export: {
    container: string;
    filename_pattern: string;
    output_directory: string | null;
  };
  profile_id?: string | null;
  warnings?: string[];
}

export interface ClipConfigurationOut {
  clip_id: string;
  configuration: ClipConfiguration;
  source_width: number | null;
  source_height: number | null;
  source_fps: number | null;
  estimated_file_size_bytes: number | null;
  validation: {
    ok: boolean;
    errors: string[];
    warnings: string[];
    aspect_ratio?: string;
    width?: number;
    height?: number;
  };
}

export interface ExportProfile {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  config_json: ClipConfiguration;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface AspectPreset {
  key: string;
  label: string;
  aspect_ratio: string;
  recommended_use: string;
  default_width: number;
  default_height: number;
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

export interface GenerationDurationConfig {
  min_duration: number;
  max_duration: number;
  clip_count: number;
  auto_clip_count: boolean;
}

export interface GenerationAnalysisConfig {
  language: string | null;
  whisper_model: string;
  ollama_model: string | null;
  force_retranscribe: boolean;
  sensitivity: 'low' | 'medium' | 'high';
  content_category: string;
  auto_detect_content_type: boolean;
}

export interface GenerationAudioConfig {
  mode: 'preserve' | 'remove' | 'replace' | 'music' | 'voiceover';
  notes: string;
}

export interface GenerationConfiguration {
  schema_version: number;
  duration: GenerationDurationConfig;
  subtitles: ClipConfiguration['subtitles'];
  video: ClipConfiguration['video'];
  reframe: ClipConfiguration['reframe'];
  audio: GenerationAudioConfig;
  export_audio: ClipConfiguration['audio'];
  export: ClipConfiguration['export'];
  analysis: GenerationAnalysisConfig;
  profile_id?: string | null;
  profile_slug?: string | null;
}

export interface GenerationConfigurationOut {
  video_id: string;
  configuration: GenerationConfiguration;
  validation: {
    ok: boolean;
    errors: string[];
    warnings: string[];
    [key: string]: unknown;
  };
  summary: string[];
}

export interface GenerationProfile {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  config_json: GenerationConfiguration;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export function defaultSubtitleStyle(): SubtitleStyleConfig {
  return {
    font_family: 'Montserrat',
    font_size: 64,
    font_weight: 'bold',
    text_color: '#FFFFFF',
    highlight_color: '#FFE600',
    outline_color: '#000000',
    outline_width: 3,
    shadow: 2,
    opacity: 1,
    alignment: 'center',
    position: 'bottom',
    custom_vertical: 0.85,
    margin_h: 40,
    max_chars_per_line: 28,
    max_lines: 2,
    animation: 'word',
    uppercase: false,
    safe_area: 'tiktok',
  };
}

export function defaultGenerationConfiguration(): GenerationConfiguration {
  return {
    schema_version: 1,
    duration: {
      min_duration: 12,
      max_duration: 30,
      clip_count: 5,
      auto_clip_count: false,
    },
    subtitles: {
      enabled: true,
      preset_slug: 'hormozi',
      style: defaultSubtitleStyle(),
      segments: null,
    },
    video: {
      aspect_ratio: '9:16',
      resolution_label: '1080p',
      width: 1080,
      height: 1920,
      fps: 30,
      preserve_source_fps: false,
      quality_preset: 'balanced',
      crf: 18,
      codec: 'h264',
      encoder: 'auto',
    },
    reframe: {
      mode: 'smart_crop',
      background_color: '#000000',
      focal_x: 0.5,
      focal_y: 0.5,
      enable_face_detection: true,
      manual_crop: null,
    },
    audio: {
      mode: 'preserve',
      notes: '',
    },
    export_audio: {
      codec: 'aac',
      bitrate_kbps: 192,
      volume: 1,
    },
    export: {
      container: 'mp4',
      filename_pattern: '{title}_{id8}',
      output_directory: null,
    },
    analysis: {
      language: null,
      whisper_model: 'small',
      ollama_model: null,
      force_retranscribe: false,
      sensitivity: 'medium',
      content_category: 'auto',
      auto_detect_content_type: true,
    },
    profile_id: null,
    profile_slug: null,
  };
}
