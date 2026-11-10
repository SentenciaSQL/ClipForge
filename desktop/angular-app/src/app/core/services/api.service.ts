import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AppSettings,
  AudioMixSettings,
  AudioStudioState,
  AudioTrack,
  Clip,
  DashboardStats,
  Highlight,
  ProcessingJob,
  Project,
  SourceVideo,
  SubtitlePreset,
  Transcription,
  VideoImportResponse,
  VideoMetadata,
} from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  readonly baseUrl = 'http://127.0.0.1:8000/api';

  getHealth(): Observable<{ status: string; version: string; hardware: Record<string, unknown> }> {
    return this.http.get<{ status: string; version: string; hardware: Record<string, unknown> }>(
      `${this.baseUrl}/health`
    );
  }

  getDashboard(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.baseUrl}/dashboard`);
  }

  listProjects(): Observable<Project[]> {
    return this.http.get<Project[]>(`${this.baseUrl}/projects`);
  }

  createProject(name: string, description?: string): Observable<Project> {
    return this.http.post<Project>(`${this.baseUrl}/projects`, { name, description });
  }

  getProject(id: string): Observable<Project> {
    return this.http.get<Project>(`${this.baseUrl}/projects/${id}`);
  }

  deleteProject(id: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/projects/${id}`);
  }

  listVideos(projectId?: string): Observable<SourceVideo[]> {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    return this.http.get<SourceVideo[]>(`${this.baseUrl}/videos${query}`);
  }

  importVideo(file: File, projectId?: string, projectName?: string): Observable<VideoImportResponse> {
    const form = new FormData();
    form.append('file', file);
    if (projectId) {
      form.append('project_id', projectId);
    }
    if (projectName) {
      form.append('project_name', projectName);
    }
    return this.http.post<VideoImportResponse>(`${this.baseUrl}/videos/import`, form);
  }

  getVideoMetadata(videoId: string): Observable<VideoMetadata> {
    return this.http.get<VideoMetadata>(`${this.baseUrl}/videos/${videoId}/metadata`);
  }

  analyzeVideo(videoId: string, body: Record<string, unknown> = {}): Observable<ProcessingJob> {
    return this.http.post<ProcessingJob>(`${this.baseUrl}/videos/${videoId}/analyze`, body);
  }

  transcribeVideo(
    videoId: string,
    body: { language?: string | null; whisper_model?: string | null; force?: boolean } = {}
  ): Observable<ProcessingJob> {
    return this.http.post<ProcessingJob>(`${this.baseUrl}/videos/${videoId}/transcribe`, body);
  }

  getVideoTranscription(videoId: string, includeDetails = true): Observable<Transcription> {
    return this.http.get<Transcription>(
      `${this.baseUrl}/videos/${videoId}/transcription?include_details=${includeDetails}`
    );
  }

  getVideoHighlights(videoId: string, selectedOnly = false): Observable<Highlight[]> {
    return this.http.get<Highlight[]>(
      `${this.baseUrl}/videos/${videoId}/highlights?selected_only=${selectedOnly}`
    );
  }

  getVideoClips(videoId: string): Observable<Clip[]> {
    return this.http.get<Clip[]>(`${this.baseUrl}/videos/${videoId}/clips`);
  }

  getProjectClips(projectId: string): Observable<Clip[]> {
    return this.http.get<Clip[]>(`${this.baseUrl}/projects/${projectId}/clips`);
  }

  renderClip(
    clipId: string,
    body: { reframing_mode?: string; subtitle_preset?: string; burn_subtitles?: boolean } = {}
  ): Observable<ProcessingJob> {
    return this.http.post<ProcessingJob>(`${this.baseUrl}/clips/${clipId}/render`, body);
  }

  exportClips(clipIds: string[]): Observable<ProcessingJob> {
    return this.http.post<ProcessingJob>(`${this.baseUrl}/clips/export`, {
      clip_ids: clipIds,
      render_if_needed: true,
    });
  }

  deleteClip(clipId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/clips/${clipId}`);
  }

  getAudioStudio(clipId: string): Observable<AudioStudioState> {
    return this.http.get<AudioStudioState>(`${this.baseUrl}/clips/${clipId}/audio`);
  }

  updateMixSettings(clipId: string, settings: AudioMixSettings): Observable<AudioMixSettings> {
    return this.http.put<AudioMixSettings>(`${this.baseUrl}/clips/${clipId}/audio/mix-settings`, settings);
  }

  applyAudioPreset(clipId: string, presetSlug: string): Observable<AudioStudioState> {
    return this.http.post<AudioStudioState>(`${this.baseUrl}/clips/${clipId}/audio/apply-preset`, {
      preset_slug: presetSlug,
    });
  }

  updateAudioTrack(
    trackId: string,
    patch: Partial<AudioTrack>
  ): Observable<AudioTrack> {
    return this.http.patch<AudioTrack>(`${this.baseUrl}/audio-tracks/${trackId}`, patch);
  }

  deleteAudioTrack(trackId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/audio-tracks/${trackId}`);
  }

  uploadAudioTrack(
    clipId: string,
    trackType: string,
    file: File,
    options: { label?: string; volume?: number; ducking_enabled?: boolean } = {}
  ): Observable<AudioTrack> {
    const form = new FormData();
    form.append('track_type', trackType);
    form.append('file', file);
    if (options.label) form.append('label', options.label);
    if (options.volume != null) form.append('volume', String(options.volume));
    if (options.ducking_enabled != null) form.append('ducking_enabled', String(options.ducking_enabled));
    return this.http.post<AudioTrack>(`${this.baseUrl}/clips/${clipId}/audio-tracks`, form);
  }

  listSubtitlePresets(): Observable<SubtitlePreset[]> {
    return this.http.get<SubtitlePreset[]>(`${this.baseUrl}/subtitle-presets`);
  }

  listJobs(): Observable<ProcessingJob[]> {
    return this.http.get<ProcessingJob[]>(`${this.baseUrl}/jobs`);
  }

  getJob(id: string): Observable<ProcessingJob> {
    return this.http.get<ProcessingJob>(`${this.baseUrl}/jobs/${id}`);
  }

  cancelJob(id: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.baseUrl}/jobs/${id}/cancel`, {});
  }

  getSettings(): Observable<AppSettings> {
    return this.http.get<AppSettings>(`${this.baseUrl}/settings`);
  }

  updateSettings(patch: Partial<AppSettings>): Observable<AppSettings> {
    return this.http.patch<AppSettings>(`${this.baseUrl}/settings`, patch);
  }
}
