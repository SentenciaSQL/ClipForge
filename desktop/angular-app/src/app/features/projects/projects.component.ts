import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Project, SourceVideo } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-projects',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DatePipe],
  template: `
    <div class="space-y-6">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div class="avc-label">Library</div>
          <h1 class="avc-title mt-1">Projects</h1>
        </div>
        <form class="flex gap-2" (ngSubmit)="create()">
          <input class="avc-input w-56" [(ngModel)]="newName" name="name" placeholder="New project name" required />
          <button class="avc-btn-primary" type="submit">Create</button>
        </form>
      </header>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <section class="grid gap-4 lg:grid-cols-2">
        <article class="avc-panel p-4" *ngFor="let project of projects()">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="font-display text-lg font-semibold">{{ project.name }}</h2>
              <p class="mt-1 text-xs text-muted">
                {{ project.video_count }} videos · updated {{ project.updated_at | date: 'short' }}
              </p>
            </div>
            <button class="avc-btn-ghost text-xs" type="button" (click)="remove(project.id)">Delete</button>
          </div>
          <button class="avc-btn-ghost mt-4 w-full" type="button" (click)="loadVideos(project.id)">
            Show videos
          </button>
          <div class="mt-3 space-y-2" *ngIf="videosByProject()[project.id] as videos">
            <div class="rounded-lg border border-line bg-canvas/50 px-3 py-2 text-sm" *ngFor="let video of videos">
              <div class="font-medium">{{ video.original_filename }}</div>
              <div class="text-xs text-muted">
                {{ video.width }}×{{ video.height }} · {{ video.video_codec }} · {{ video.status }}
              </div>
            </div>
            <p class="text-xs text-muted" *ngIf="!videos.length">No videos in this project.</p>
          </div>
        </article>
      </section>
    </div>
  `,
})
export class ProjectsComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly projects = signal<Project[]>([]);
  readonly videosByProject = signal<Record<string, SourceVideo[]>>({});
  readonly error = signal<string | null>(null);
  newName = '';

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: (err) => this.error.set(err?.message || 'Failed to load projects'),
    });
  }

  create(): void {
    const name = this.newName.trim();
    if (!name) {
      return;
    }
    this.api.createProject(name).subscribe({
      next: () => {
        this.newName = '';
        this.refresh();
      },
      error: (err) => this.error.set(err?.error?.detail || 'Create failed'),
    });
  }

  remove(id: string): void {
    this.api.deleteProject(id).subscribe({
      next: () => this.refresh(),
      error: (err) => this.error.set(err?.error?.detail || 'Delete failed'),
    });
  }

  loadVideos(projectId: string): void {
    this.api.listVideos(projectId).subscribe({
      next: (videos) =>
        this.videosByProject.update((current) => ({
          ...current,
          [projectId]: videos,
        })),
      error: (err) => this.error.set(err?.message || 'Failed to load videos'),
    });
  }
}
