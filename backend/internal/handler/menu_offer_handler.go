package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuOfferHandler struct {
	service *service.MenuOfferService
}

func NewMenuOfferHandler(service *service.MenuOfferService) *MenuOfferHandler {
	return &MenuOfferHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu offers
// @Description  Mengembalikan daftar semua menu offers
// @Tags         MenuOffers
// @Produce      json
// @Success      200  {array}  models.MenuOffer
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-offers [get]
func (h *MenuOfferHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu offer by ID
// @Description  Mengembalikan satu menu offer berdasarkan ID
// @Tags         MenuOffers
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuOffer
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-offers/{id} [get]
func (h *MenuOfferHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	item, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if item == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	respondWithJSON(w, http.StatusOK, item)
}
