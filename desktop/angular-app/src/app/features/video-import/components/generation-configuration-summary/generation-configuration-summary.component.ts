import { NgFor, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-generation-configuration-summary',
  standalone: true,
  imports: [NgFor, NgIf],
  templateUrl: './generation-configuration-summary.component.html',
  styleUrl: './generation-configuration-summary.component.scss',
})
export class GenerationConfigurationSummaryComponent {
  @Input() summary: string[] = [];
  @Input() warnings: string[] = [];
  @Input() errors: string[] = [];
  @Input() busy = false;
  @Output() back = new EventEmitter<void>();
  @Output() generate = new EventEmitter<void>();
}
