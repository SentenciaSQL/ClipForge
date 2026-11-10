import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  LucideAudioLines,
  LucideClapperboard,
  LucideFolderOpen,
  LucideLayoutDashboard,
  LucideLibrary,
  LucideSettings,
  LucideSparkles,
  LucideSubtitles,
  LucideUpload,
} from '@lucide/angular';

@Component({
  selector: 'app-shell-layout',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    LucideLayoutDashboard,
    LucideUpload,
    LucideFolderOpen,
    LucideSparkles,
    LucideClapperboard,
    LucideSubtitles,
    LucideAudioLines,
    LucideLibrary,
    LucideSettings,
  ],
  template: `
    <div class="flex min-h-screen">
      <aside class="flex w-64 shrink-0 flex-col border-r border-line bg-panel/80 px-4 py-5">
        <div class="mb-8 px-2">
          <div class="font-display text-lg font-semibold tracking-tight text-ink">AI Video Clipper</div>
          <div class="mt-1 text-xs text-muted">Local · Private · GPU-ready</div>
        </div>

        <nav class="flex flex-1 flex-col gap-1">
          <a
            routerLink="/dashboard"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideLayoutDashboard class="h-[18px] w-[18px]"></svg>
            <span>Dashboard</span>
          </a>
          <a
            routerLink="/import"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideUpload class="h-[18px] w-[18px]"></svg>
            <span>Import</span>
          </a>
          <a
            routerLink="/projects"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideFolderOpen class="h-[18px] w-[18px]"></svg>
            <span>Projects</span>
          </a>
          <a
            routerLink="/generate"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideSparkles class="h-[18px] w-[18px]"></svg>
            <span>Generate</span>
          </a>
          <a
            routerLink="/clips"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideClapperboard class="h-[18px] w-[18px]"></svg>
            <span>Clips Studio</span>
          </a>
          <a
            routerLink="/subtitles"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideSubtitles class="h-[18px] w-[18px]"></svg>
            <span>Subtitles</span>
          </a>
          <a
            routerLink="/audio"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideAudioLines class="h-[18px] w-[18px]"></svg>
            <span>Audio Studio</span>
          </a>
          <a
            routerLink="/exports"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideLibrary class="h-[18px] w-[18px]"></svg>
            <span>Exports</span>
          </a>
          <a
            routerLink="/settings"
            routerLinkActive="bg-accentSoft/40 text-accent border-accent/30"
            class="flex items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm text-muted transition hover:border-line hover:text-ink"
          >
            <svg lucideSettings class="h-[18px] w-[18px]"></svg>
            <span>Settings</span>
          </a>
        </nav>

        <div class="mt-4 rounded-xl border border-line bg-canvas/60 p-3 text-xs text-muted">
          Phase 1 foundation active. Transcription and AI clipping unlock in later phases.
        </div>
      </aside>

      <main class="min-w-0 flex-1 overflow-auto">
        <div class="mx-auto max-w-7xl px-6 py-6">
          <router-outlet />
        </div>
      </main>
    </div>
  `,
})
export class ShellLayoutComponent {}
