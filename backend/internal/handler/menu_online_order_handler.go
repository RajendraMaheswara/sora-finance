package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuOnlineOrderHandler struct {
	service *service.MenuOnlineOrderService
}

func NewMenuOnlineOrderHandler(service *service.MenuOnlineOrderService) *MenuOnlineOrderHandler {
	return &MenuOnlineOrderHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu online orders
// @Description  Mengembalikan daftar semua menu online orders
// @Tags         MenuOnlineOrders
// @Produce      json
// @Success      200  {array}  models.MenuOnlineOrder
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-online-orders [get]
func (h *MenuOnlineOrderHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu online order by ID
// @Description  Mengembalikan satu menu online order berdasarkan ID
// @Tags         MenuOnlineOrders
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuOnlineOrder
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-online-orders/{id} [get]
func (h *MenuOnlineOrderHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
