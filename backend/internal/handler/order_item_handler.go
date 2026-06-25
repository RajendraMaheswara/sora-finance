package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type OrderItemHandler struct {
	service *service.OrderItemService
}

func NewOrderItemHandler(service *service.OrderItemService) *OrderItemHandler {
	return &OrderItemHandler{service: service}
}

// GetAll godoc
// @Summary      Get all order items
// @Description  Mengembalikan daftar semua order items
// @Tags         OrderItems
// @Produce      json
// @Success      200  {array}  models.OrderItem
// @Failure      500  {object}  map[string]interface{}
// @Router       /order-items [get]
func (h *OrderItemHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get order item by ID
// @Description  Mengembalikan satu order item berdasarkan ID
// @Tags         OrderItems
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.OrderItem
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /order-items/{id} [get]
func (h *OrderItemHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
