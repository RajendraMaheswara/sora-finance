package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuPackagingHandler struct {
	service *service.MenuPackagingService
}

func NewMenuPackagingHandler(service *service.MenuPackagingService) *MenuPackagingHandler {
	return &MenuPackagingHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu packagings
// @Description  Mengembalikan daftar semua menu packagings
// @Tags         MenuPackagings
// @Produce      json
// @Success      200  {array}  models.MenuPackaging
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-packagings [get]
func (h *MenuPackagingHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu packaging by ID
// @Description  Mengembalikan satu menu packaging berdasarkan ID
// @Tags         MenuPackagings
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuPackaging
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-packagings/{id} [get]
func (h *MenuPackagingHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
