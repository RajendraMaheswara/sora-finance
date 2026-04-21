package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type StoreHandler struct {
	service *service.StoreService
}

func NewStoreHandler(service *service.StoreService) *StoreHandler {
	return &StoreHandler{service: service}
}

// GetAll godoc
// @Summary      Get all stores
// @Description  Mengembalikan daftar semua toko
// @Tags         Stores
// @Produce      json
// @Success      200  {array}  models.Store
// @Failure      500  {object}  map[string]interface{}
// @Router       /stores [get]
func (h *StoreHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	stores, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, stores)
}

// GetByID godoc
// @Summary      Get store by ID
// @Description  Mengembalikan satu toko berdasarkan ID
// @Tags         Stores
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.Store
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /stores/{id} [get]
func (h *StoreHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	store, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if store == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, store)
}