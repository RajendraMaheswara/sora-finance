package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuOfferDetailHandler struct {
	service *service.MenuOfferDetailService
}

func NewMenuOfferDetailHandler(service *service.MenuOfferDetailService) *MenuOfferDetailHandler {
	return &MenuOfferDetailHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu offer details
// @Description  Mengembalikan daftar semua menu offer details
// @Tags         MenuOfferDetails
// @Produce      json
// @Success      200  {array}  models.MenuOfferDetail
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-offer-details [get]
func (h *MenuOfferDetailHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu offer detail by ID
// @Description  Mengembalikan satu menu offer detail berdasarkan ID
// @Tags         MenuOfferDetails
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuOfferDetail
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-offer-details/{id} [get]
func (h *MenuOfferDetailHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
