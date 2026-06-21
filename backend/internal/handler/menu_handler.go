package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuHandler struct {
	service *service.MenuService
}

func NewMenuHandler(service *service.MenuService) *MenuHandler {
	return &MenuHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menus
// @Description  Mengembalikan daftar semua menus
// @Tags         Menus
// @Produce      json
// @Success      200  {array}  models.Menu
// @Failure      500  {object}  map[string]interface{}
// @Router       /menus [get]
func (h *MenuHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu by ID
// @Description  Mengembalikan satu menu berdasarkan ID
// @Tags         Menus
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.Menu
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menus/{id} [get]
func (h *MenuHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
