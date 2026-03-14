import { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";

interface TimeSliderProps {
  startYear?: number;
  endYear?: number;
  onChange?: (period: string) => void;
  className?: string;
}

export default function TimeSlider({
  startYear = 2010,
  endYear = 2026,
  onChange,
  className = "",
}: TimeSliderProps) {
  const totalMonths = (endYear - startYear) * 12;
  const [currentMonth, setCurrentMonth] = useState(totalMonths);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const monthToLabel = useCallback(
    (month: number) => {
      const year = startYear + Math.floor(month / 12);
      const m = month % 12;
      const monthNames = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
      ];
      return `${monthNames[m]} ${year}`;
    },
    [startYear]
  );

  const monthToPeriod = useCallback(
    (month: number) => {
      const year = startYear + Math.floor(month / 12);
      const m = (month % 12) + 1;
      return `${year}-${String(m).padStart(2, "0")}`;
    },
    [startYear]
  );

  useEffect(() => {
    onChange?.(monthToPeriod(currentMonth));
  }, [currentMonth, onChange, monthToPeriod]);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setCurrentMonth((prev) => {
          if (prev >= totalMonths) {
            setPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 150);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, totalMonths]);

  const handlePlayPause = () => {
    if (currentMonth >= totalMonths && !playing) {
      setCurrentMonth(0);
      setPlaying(true);
    } else {
      setPlaying(!playing);
    }
  };

  // Generate year tick marks
  const years = Array.from(
    { length: endYear - startYear + 1 },
    (_, i) => startYear + i
  );

  return (
    <div className={`glass-panel px-6 py-4 ${className}`}>
      <div className="flex items-center gap-4">
        {/* Play/Pause button */}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={handlePlayPause}
          className="w-10 h-10 rounded-full bg-ocean-600 hover:bg-ocean-500 flex items-center justify-center text-white transition-colors shrink-0"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          ) : (
            <svg className="w-4 h-4 ml-0.5" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5,3 19,12 5,21" />
            </svg>
          )}
        </motion.button>

        {/* Slider area */}
        <div className="flex-1 relative">
          {/* Current date label */}
          <div className="text-center mb-2">
            <motion.span
              key={currentMonth}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-sm font-medium text-ocean-400 tabular-nums"
            >
              {monthToLabel(currentMonth)}
            </motion.span>
          </div>

          {/* Range input */}
          <input
            type="range"
            min={0}
            max={totalMonths}
            value={currentMonth}
            onChange={(e) => {
              setCurrentMonth(Number(e.target.value));
              setPlaying(false);
            }}
            aria-label={`Time period slider, currently ${monthToLabel(currentMonth)}`}
            className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-ocean-500"
          />

          {/* Year labels */}
          <div className="flex justify-between mt-1.5">
            {years
              .filter((_, i) => i % 2 === 0 || years.length <= 10)
              .map((year) => (
                <span key={year} className="text-[10px] text-gray-400">
                  {year}
                </span>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
