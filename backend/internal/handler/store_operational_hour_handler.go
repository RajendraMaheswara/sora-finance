package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type StoreOperationalHourHandler struct {
	service *service.StoreOperationalHourService
}

func NewStoreOperationalHourHandler(service *service.StoreOperationalHourService) *StoreOperationalHourHandler {
	return &StoreOperationalHourHandler{service: service}
}

// GetAll godoc
// @Summary      Get all store operational hours
// @Description  Mengembalikan daftar semua store operational hours
// @Tags         StoreOperationalHours
// @Produce      json
// @Success      200  {array}  models.StoreOperationalHour
// @Failure      500  {object}  map[string]interface{}
// @Router       /store-operational-hours [get]
func (h *StoreOperationalHourHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get store operational hour by ID
// @Description  Mengembalikan satu store operational hour berdasarkan ID
// @Tags         StoreOperationalHours
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.StoreOperationalHour
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /store-operational-hours/{id} [get]
func (h *StoreOperationalHourHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	item, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if item == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, item)
}
