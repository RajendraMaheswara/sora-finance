package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuVariantHandler struct {
	service *service.MenuVariantService
}

func NewMenuVariantHandler(service *service.MenuVariantService) *MenuVariantHandler {
	return &MenuVariantHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu variants
// @Description  Mengembalikan daftar semua menu variants
// @Tags         MenuVariants
// @Produce      json
// @Success      200  {array}  models.MenuVariant
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-variants [get]
func (h *MenuVariantHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu variant by ID
// @Description  Mengembalikan satu menu variant berdasarkan ID
// @Tags         MenuVariants
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuVariant
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-variants/{id} [get]
func (h *MenuVariantHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
