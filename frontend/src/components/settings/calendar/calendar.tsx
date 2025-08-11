'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  isSameMonth,
  isSameDay,
  format,
  isToday,
} from 'date-fns';

interface CalendarProps {
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  currentMonth: Date;
  onMonthChange?: (date: Date) => void;
  events?: Array<{
    date: Date;
    title: string;
    color?: string;
  }>;
}

export const Calendar: React.FC<CalendarProps> = ({
  selectedDate,
  onSelectDate,
  currentMonth,
  onMonthChange,
  events = [],
}) => {
  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(monthStart);
  const startDate = startOfWeek(monthStart);
  const endDate = endOfWeek(monthEnd);

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const generateDates = () => {
    const dateArray = [];
    let currentDate = startDate;

    while (currentDate <= endDate) {
      dateArray.push(currentDate);
      currentDate = addDays(currentDate, 1);
    }

    return dateArray;
  };

  const dates = generateDates();

  const getEventsForDate = (date: Date) => {
    return events.filter(event => isSameDay(event.date, date));
  };

  return (
    <div className="w-full">
      {/* Week days header */}
      <div className="grid grid-cols-7 mb-2">
        {weekDays.map(day => (
          <div
            key={day}
            className="text-center text-sm font-medium text-muted-foreground py-2"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-px bg-border rounded-lg overflow-hidden">
        {dates.map((date, index) => {
          const dayEvents = getEventsForDate(date);
          const isSelected = isSameDay(date, selectedDate);
          const isCurrentMonth = isSameMonth(date, currentMonth);
          const isTodayDate = isToday(date);

          return (
            <button
              key={index}
              onClick={() => onSelectDate(date)}
              className={cn(
                'relative min-h-[100px] p-2 bg-background hover:bg-accent transition-colors text-left',
                !isCurrentMonth && 'text-muted-foreground bg-muted/30',
                isSelected && 'bg-primary/10 hover:bg-primary/20',
                isTodayDate && 'ring-2 ring-primary ring-inset'
              )}
            >
              <div className="flex items-start justify-between">
                <span
                  className={cn(
                    'inline-flex items-center justify-center w-7 h-7 text-sm font-medium rounded-full',
                    isTodayDate && 'bg-primary text-primary-foreground',
                    isSelected && !isTodayDate && 'bg-primary/20'
                  )}
                >
                  {format(date, 'd')}
                </span>
                {dayEvents.length > 0 && (
                  <div className="flex gap-1">
                    {dayEvents.slice(0, 3).map((event, i) => (
                      <div
                        key={i}
                        className={cn(
                          'w-1.5 h-1.5 rounded-full',
                          event.color || 'bg-blue-500'
                        )}
                      />
                    ))}
                  </div>
                )}
              </div>
              
              {/* Event preview */}
              <div className="mt-1 space-y-1">
                {dayEvents.slice(0, 2).map((event, i) => (
                  <div
                    key={i}
                    className="text-xs truncate px-1 py-0.5 rounded bg-primary/10 text-primary"
                  >
                    {event.title}
                  </div>
                ))}
                {dayEvents.length > 2 && (
                  <div className="text-xs text-muted-foreground px-1">
                    +{dayEvents.length - 2} more
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};