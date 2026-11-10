import { Component } from '@angular/core';

@Component({
  selector: 'app-export-library',
  standalone: true,
  template: `
    <div class="space-y-4">
      <div class="avc-label">Deliverables</div>
      <h1 class="avc-title">Export Library</h1>
      <p class="max-w-2xl text-sm text-muted">
        Finished vertical shorts will appear here for preview, batch export, and folder open actions.
      </p>
      <div class="avc-panel p-8 text-sm text-muted">Export folder: workspace/exports</div>
    </div>
  `,
})
export class ExportLibraryComponent {}
