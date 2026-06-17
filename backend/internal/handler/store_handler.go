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
// @Summary      Dapatkan semua store
// @Description  Mengembalikan daftar semua store yang aktif
// @Tags         Stores
// @Produce      json
// @Success      200  {array}  models.Store
// @Failure      500  {object}  map[string]interface{}
// @Router       /stores [get]
func (h *StoreHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	stores, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, stores)
}

// GetByID godoc
// @Summary      Dapatkan store berdasarkan ID
// @Description  Mengembalikan satu store berdasarkan UUID
// @Tags         Stores
// @Produce      json
// @Param        id   path      string  true  "UUID store"
// @Success      200  {object}  models.Store
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /stores/{id} [get]
func (h *StoreHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	store, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}
	if store == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "store not found"})
		return
	}
	respondWithJSON(w, http.StatusOK, store)
}
