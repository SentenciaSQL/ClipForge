import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-clip-generation',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Pipeline</div>
        <h1 class="avc-title mt-1">Clip Generation</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Defaults for automatic clipping. Full Whisper + Ollama execution arrives in Phase 2–3.
          You can already queue analysis jobs from Import.
        </p>
      </header>

      <form class="avc-panel grid gap-4 p-5 md:grid-cols-2">
        <label class="text-sm">
          <span class="avc-label">Min duration (s)</span>
          <input class="avc-input mt-2" type="number" [(ngModel)]="minDuration" name="min" min="12" max="30" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Max duration (s)</span>
          <input class="avc-input mt-2" type="number" [(ngModel)]="maxDuration" name="max" min="12" max="30" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Number of clips</span>
          <input class="avc-input mt-2" type="number" [(ngModel)]="clipCount" name="count" min="1" max="50" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Language</span>
          <select class="avc-input mt-2" [(ngModel)]="language" name="language">
            <option value="auto">Automatic</option>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="pt">Portuguese</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Subtitle preset</span>
          <select class="avc-input mt-2" [(ngModel)]="subtitlePreset" name="preset">
            <option value="hormozi">Hormozi</option>
            <option value="karaoke">Karaoke</option>
            <option value="tiktok">TikTok</option>
            <option value="minimal">Minimal</option>
            <option value="professional">Professional</option>
            <option value="custom">Custom</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Reframing</span>
          <select class="avc-input mt-2" [(ngModel)]="reframe" name="reframe">
            <option value="auto">Automatic</option>
            <option value="smart_crop">Smart crop</option>
            <option value="center_crop">Center crop</option>
            <option value="blurred_bg">Blurred background</option>
          </select>
        </label>
      </form>
    </div>
  `,
})
export class ClipGenerationComponent {
  minDuration = 12;
  maxDuration = 30;
  clipCount = 5;
  language = 'auto';
  subtitlePreset = 'hormozi';
  reframe = 'auto';
}
