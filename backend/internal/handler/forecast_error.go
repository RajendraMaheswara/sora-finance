package handler

import (
	"errors"
	"net/http"
	"strings"

	"sora-finance-api/internal/service"
)

func forecastErrorStatus(err error) int {
	if err == nil {
		return http.StatusInternalServerError
	}
	message := strings.ToLower(err.Error())
	switch {
	case errors.Is(err, service.ErrInvalidInput):
		return http.StatusBadRequest
	case strings.Contains(message, "forbidden"):
		return http.StatusForbidden
	case strings.Contains(message, "not found"):
		return http.StatusNotFound
	case strings.Contains(message, "unauthorized"):
		return http.StatusUnauthorized
	case strings.Contains(message, "required"),
		strings.Contains(message, "invalid"),
		strings.Contains(message, "cannot"),
		strings.Contains(message, "must"):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}

func forecastSafeErrorMessage(err error) string {
	if forecastErrorStatus(err) == http.StatusInternalServerError {
		return "internal server error"
	}
	if err == nil {
		return "internal server error"
	}
	return err.Error()
}

func respondForecastError(w http.ResponseWriter, err error) {
	respondWithJSON(w, forecastErrorStatus(err), map[string]string{"error": forecastSafeErrorMessage(err)})
}
