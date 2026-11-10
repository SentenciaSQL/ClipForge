import { DatePipe, DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DashboardStats } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [NgIf, NgFor, RouterLink, DatePipe, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div class="avc-label">Overview</div>
          <h1 class="avc-title mt-1">Dashboard</h1>
          <p class="mt-2 max-w-2xl text-sm text-muted">
            Local processing status, recent projects, and hardware readiness for AI Video Clipper.
          </p>
        </div>
        <a routerLink="/import" class="avc-btn-primary">Import video</a>
      </header>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" *ngIf="stats() as s">
        <article class="avc-panel p-4" *ngFor="let card of cards(s)">
          <div class="avc-label">{{ card.label }}</div>
          <div class="mt-3 font-display text-3xl font-semibold">{{ card.value }}</div>
        </article>
      </section>

      <section class="grid gap-4 lg:grid-cols-2" *ngIf="stats() as s">
        <article class="avc-panel p-5">
          <div class="avc-label">Recent projects</div>
          <div class="mt-4 space-y-3" *ngIf="s.recent_projects.length; else noProjects">
            <a
              class="flex items-center justify-between rounded-xl border border-line bg-canvas/40 px-3 py-3 transition hover:border-accent/40"
              *ngFor="let project of s.recent_projects"
              [routerLink]="['/projects']"
            >
              <div>
                <div class="font-medium">{{ project.name }}</div>
                <div class="text-xs text-muted">
                  {{ project.video_count }} videos · {{ project.clip_count }} clips
                </div>
              </div>
              <div class="text-xs text-muted">{{ project.updated_at | date: 'short' }}</div>
            </a>
          </div>
          <ng-template #noProjects>
            <p class="mt-4 text-sm text-muted">No projects yet. Import a video to create one.</p>
          </ng-template>
        </article>

        <article class="avc-panel p-5">
          <div class="avc-label">Hardware</div>
          <dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt class="text-muted">Device</dt>
              <dd class="mt-1 font-medium">{{ s.hardware['recommended_device'] || 'cpu' }}</dd>
            </div>
            <div>
              <dt class="text-muted">FFmpeg</dt>
              <dd class="mt-1 font-medium">{{ s.hardware['ffmpeg_available'] ? 'Ready' : 'Missing' }}</dd>
            </div>
            <div>
              <dt class="text-muted">CUDA</dt>
              <dd class="mt-1 font-medium">{{ s.hardware['cuda_available'] ? 'Available' : 'Unavailable' }}</dd>
            </div>
            <div>
              <dt class="text-muted">Ollama</dt>
              <dd class="mt-1 font-medium">{{ s.hardware['ollama_available'] ? 'Online' : 'Offline' }}</dd>
            </div>
            <div class="col-span-2">
              <dt class="text-muted">GPU</dt>
              <dd class="mt-1 font-medium">{{ s.hardware['gpu_name'] || 'None detected' }}</dd>
            </div>
          </dl>
          <ul class="mt-4 space-y-1 text-xs text-warn" *ngIf="asNotes(s.hardware['notes']).length">
            <li *ngFor="let note of asNotes(s.hardware['notes'])">{{ note }}</li>
          </ul>
        </article>
      </section>

      <section class="avc-panel p-5" *ngIf="stats() as s">
        <div class="avc-label">Recent jobs</div>
        <div class="mt-4 overflow-x-auto" *ngIf="s.recent_jobs.length; else noJobs">
          <table class="w-full min-w-[640px] text-left text-sm">
            <thead class="text-xs uppercase tracking-wide text-muted">
              <tr>
                <th class="pb-2 font-medium">Type</th>
                <th class="pb-2 font-medium">Status</th>
                <th class="pb-2 font-medium">Stage</th>
                <th class="pb-2 font-medium">Progress</th>
                <th class="pb-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-t border-line" *ngFor="let job of s.recent_jobs">
                <td class="py-3">{{ job.job_type }}</td>
                <td class="py-3">{{ job.status }}</td>
                <td class="py-3">{{ job.current_stage || '—' }}</td>
                <td class="py-3">{{ job.progress | number: '1.0-0' }}%</td>
                <td class="py-3 text-muted">{{ job.created_at | date: 'short' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <ng-template #noJobs>
          <p class="mt-4 text-sm text-muted">No processing jobs yet.</p>
        </ng-template>
      </section>
    </div>
  `,
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly stats = signal<DashboardStats | null>(null);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.api.getDashboard().subscribe({
      next: (data) => this.stats.set(data),
      error: (err) =>
        this.error.set(
          err?.message
            ? `Backend unreachable: ${err.message}`
            : 'Backend unreachable. Start the FastAPI server on port 8000.'
        ),
    });
  }

  cards(s: DashboardStats): Array<{ label: string; value: number }> {
    return [
      { label: 'Projects', value: s.total_projects },
      { label: 'Imported videos', value: s.imported_videos },
      { label: 'Generated clips', value: s.generated_clips },
      { label: 'Active jobs', value: s.active_jobs },
    ];
  }

  asNotes(value: unknown): string[] {
    return Array.isArray(value) ? value.map(String) : [];
  }
}
