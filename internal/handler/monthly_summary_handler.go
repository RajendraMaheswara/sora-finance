package handler

import (
	"encoding/json"
	"net/http"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type MonthlySummaryHandler struct {
	service *service.MonthlySummaryService
}

func NewMonthlySummaryHandler(service *service.MonthlySummaryService) *MonthlySummaryHandler {
	return &MonthlySummaryHandler{service: service}
}

func (h *MonthlySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	summaries, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, summaries)
}

func (h *MonthlySummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	summary, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if summary == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, summary)
}

func (h *MonthlySummaryHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req models.MonthlySummary
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}
	created, err := h.service.Create(r.Context(), &req)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	respondWithJSON(w, http.StatusCreated, created)
}

func (h *MonthlySummaryHandler) Update(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	var req models.MonthlySummary
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if err := h.service.Update(r.Context(), id, &req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *MonthlySummaryHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	// Contoh: ambil deleted_by dari context (misal dari JWT). Untuk sederhana, kita hardcode sementara.
	deletedBy := uuid.MustParse("00000000-0000-0000-0000-000000000001") // ganti dengan user ID dari auth
	if err := h.service.Delete(r.Context(), id, deletedBy); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func respondWithJSON(w http.ResponseWriter, code int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(payload)
}