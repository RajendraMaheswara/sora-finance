package service

import (
	"errors"
	"strings"
	"time"
)

var ErrInvalidInput = errors.New("invalid input")

func parseDate(value string) (time.Time, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return time.Time{}, errors.New("date is required")
	}
	if parsed, err := time.Parse("2006-01-02", trimmed); err == nil {
		return parsed, nil
	}
	if parsed, err := time.Parse(time.RFC3339Nano, trimmed); err == nil {
		return parsed, nil
	}
	if parsed, err := time.Parse(time.RFC3339, trimmed); err == nil {
		return parsed, nil
	}
	return time.Time{}, errors.New("invalid date format")
}

func parseTimestampOptional(value *string) (time.Time, error) {
	if value == nil {
		return time.Now().UTC(), nil
	}
	trimmed := strings.TrimSpace(*value)
	if trimmed == "" {
		return time.Now().UTC(), nil
	}
	if parsed, err := time.Parse(time.RFC3339Nano, trimmed); err == nil {
		return parsed, nil
	}
	if parsed, err := time.Parse(time.RFC3339, trimmed); err == nil {
		return parsed, nil
	}
	if parsed, err := time.Parse("2006-01-02", trimmed); err == nil {
		return parsed, nil
	}
	return time.Time{}, errors.New("invalid timestamp format")
}
