import { Routes } from '@angular/router';

import { ShellLayoutComponent } from './shared/components/shell-layout.component';

export const routes: Routes = [
  {
    path: '',
    component: ShellLayoutComponent,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'import',
        loadComponent: () =>
          import('./features/video-import/video-import.component').then((m) => m.VideoImportComponent),
      },
      {
        path: 'projects',
        loadComponent: () =>
          import('./features/projects/projects.component').then((m) => m.ProjectsComponent),
      },
      {
        path: 'generate',
        loadComponent: () =>
          import('./features/clip-generation/clip-generation.component').then(
            (m) => m.ClipGenerationComponent
          ),
      },
      {
        path: 'clips',
        loadComponent: () =>
          import('./features/clips-studio/clips-studio.component').then((m) => m.ClipsStudioComponent),
      },
      {
        path: 'subtitles',
        loadComponent: () =>
          import('./features/subtitle-editor/subtitle-editor.component').then(
            (m) => m.SubtitleEditorComponent
          ),
      },
      {
        path: 'audio',
        loadComponent: () =>
          import('./features/audio-studio/audio-studio.component').then((m) => m.AudioStudioComponent),
      },
      {
        path: 'exports',
        loadComponent: () =>
          import('./features/export-library/export-library.component').then(
            (m) => m.ExportLibraryComponent
          ),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/settings/settings.component').then((m) => m.SettingsComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
