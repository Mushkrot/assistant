import { cn } from '@/lib/utils';
import type { Hint } from '@/types';
import { Lightbulb, Loader2 } from 'lucide-react';

interface HintsPanelProps {
  currentHint: Hint | null;
  previousHints: Hint[];
  isGenerating: boolean;
  className?: string;
}

function HintCard({
  hint,
  isCurrent = false,
}: {
  hint: Hint;
  isCurrent?: boolean;
}) {
  return (
    <div
      className={cn(
        'p-4 rounded-lg border',
        isCurrent
          ? 'bg-primary-900/30 border-primary-700/50'
          : 'bg-gray-800/50 border-gray-700/50 opacity-70'
      )}
    >
      <div className="flex items-start gap-3">
        <Lightbulb
          className={cn(
            'w-5 h-5 mt-0.5 flex-shrink-0',
            isCurrent ? 'text-primary-400' : 'text-gray-500'
          )}
        />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-gray-200 whitespace-pre-wrap">
            {hint.text}
            {!hint.isComplete && (
              <span className="typing-indicator ml-1">
                <span className="inline-block w-1 h-1 bg-current rounded-full mx-0.5" />
                <span className="inline-block w-1 h-1 bg-current rounded-full mx-0.5" />
                <span className="inline-block w-1 h-1 bg-current rounded-full mx-0.5" />
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function HintsPanel({
  currentHint,
  previousHints,
  isGenerating,
  className,
}: HintsPanelProps) {
  const hasHints = currentHint || previousHints.length > 0;

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <h2 className="text-sm font-medium text-gray-300 flex items-center gap-2">
          <Lightbulb className="w-4 h-4" />
          AI Hints
        </h2>
        {isGenerating && (
          <div className="flex items-center gap-1.5 text-primary-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="text-xs">Generating...</span>
          </div>
        )}
      </div>

      {/* Hints content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!hasHints ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Lightbulb className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm text-center">
              Hints will appear here when questions are detected
            </p>
          </div>
        ) : (
          <>
            {/* Current hint */}
            {currentHint && <HintCard hint={currentHint} isCurrent />}

            {/* Previous hints */}
            {previousHints.length > 0 && (
              <div className="space-y-2">
                {previousHints.slice(-3).map((hint) => (
                  <HintCard key={hint.id} hint={hint} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
