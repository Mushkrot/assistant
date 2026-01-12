import { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { formatTimestamp } from '@/lib/utils';
import type { TranscriptSegment } from '@/types';

interface TranscriptFeedProps {
  segments: TranscriptSegment[];
  className?: string;
}

function TranscriptMessage({ segment }: { segment: TranscriptSegment }) {
  const isMe = segment.speaker === 'ME';

  return (
    <div
      className={cn(
        'flex flex-col max-w-[80%] mb-3',
        isMe ? 'ml-auto items-end' : 'mr-auto items-start'
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className={cn(
            'text-xs font-medium px-2 py-0.5 rounded',
            isMe
              ? 'bg-blue-900/50 text-blue-300'
              : 'bg-gray-700 text-gray-300'
          )}
        >
          {isMe ? 'ME' : 'THEM'}
        </span>
        <span className="text-xs text-gray-500">
          {formatTimestamp(segment.timestamp)}
        </span>
      </div>
      <div
        className={cn(
          'px-4 py-2 rounded-2xl',
          isMe
            ? 'bg-blue-600 text-white rounded-br-sm'
            : 'bg-gray-700 text-gray-100 rounded-bl-sm',
          !segment.isComplete && 'opacity-75'
        )}
      >
        <p className="text-sm whitespace-pre-wrap break-words">
          {segment.text}
          {!segment.isComplete && (
            <span className="typing-indicator ml-1">
              <span className="inline-block w-1 h-1 bg-current rounded-full mx-0.5" />
              <span className="inline-block w-1 h-1 bg-current rounded-full mx-0.5" />
              <span className="inline-block w-1 h-1 bg-current rounded-full mx-0.5" />
            </span>
          )}
        </p>
      </div>
    </div>
  );
}

export function TranscriptFeed({ segments, className }: TranscriptFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);

  // Auto-scroll to bottom when new segments arrive
  useEffect(() => {
    if (shouldAutoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [segments]);

  // Detect if user has scrolled up
  const handleScroll = () => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      shouldAutoScrollRef.current = scrollHeight - scrollTop - clientHeight < 100;
    }
  };

  if (segments.length === 0) {
    return (
      <div className={cn('flex items-center justify-center h-full text-gray-500', className)}>
        <p className="text-sm">Waiting for conversation...</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className={cn(
        'flex flex-col p-4 overflow-y-auto transcript-feed',
        className
      )}
    >
      {segments.map((segment) => (
        <TranscriptMessage key={segment.id} segment={segment} />
      ))}
    </div>
  );
}
