package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MonthlySummaryHandler struct {
	service *service.MonthlySummaryService
}


func NewMonthlySummaryHandler(service *service.MonthlySummaryService) *MonthlySummaryHandler {
	return &MonthlySummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all monthly summaries
// @Description  Mengembalikan daftar semua ringkasan keuangan bulanan
// @Tags         MonthlySummaries
// @Produce      json
// @Success      200  {array}  models.MonthlySummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /monthly-summaries [get]
func (h *MonthlySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	summaries, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, summaries)
}

// GetByID godoc
// @Summary      Get monthly summary by ID
// @Description  Mengembalikan satu ringkasan keuangan bulanan berdasarkan ID
// @Tags         MonthlySummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MonthlySummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /monthly-summaries/{id} [get]
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