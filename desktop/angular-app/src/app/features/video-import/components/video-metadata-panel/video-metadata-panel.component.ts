import { DecimalPipe, NgIf } from '@angular/common';
import { Component, Input, inject } from '@angular/core';

import { SourceVideo } from '../../../../core/models';
import { ApiService } from '../../../../core/services/api.service';

@Component({
  selector: 'app-video-metadata-panel',
  standalone: true,
  imports: [NgIf, DecimalPipe],
  templateUrl: './video-metadata-panel.component.html',
  styleUrl: './video-metadata-panel.component.scss',
})
export class VideoMetadataPanelComponent {
  private readonly api = inject(ApiService);

  @Input({ required: true }) video!: SourceVideo;
  @Input() projectName: string | null = null;

  mediaError = false;

  thumbnailUrl(): string {
    return this.api.videoThumbnailUrl(this.video.id);
  }

  mediaUrl(): string {
    return this.api.videoMediaUrl(this.video.id);
  }

  fileSizeMb(): string {
    return (this.video.file_size_bytes / (1024 * 1024)).toFixed(2);
  }

  hasAudio(): boolean {
    if (typeof this.video.has_audio === 'boolean') {
      return this.video.has_audio;
    }
    return Boolean(this.video.audio_codec);
  }

  onMediaError(): void {
    this.mediaError = true;
  }
}
