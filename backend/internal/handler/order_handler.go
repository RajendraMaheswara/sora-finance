package handler

import (
	"net/http"
	"strconv"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type OrderHandler struct {
	service *service.OrderService
}

func NewOrderHandler(service *service.OrderService) *OrderHandler {
	return &OrderHandler{service: service}
}

// GetAll godoc
// @Summary      Get all orders
// @Description  Mengembalikan daftar semua orders
// @Tags         Orders
// @Produce      json
// @Param        page   query     int  false  "Page number"
// @Param        limit  query     int  false  "Limit per page"
// @Success      200  {array}  models.Order
// @Failure      500  {object}  map[string]interface{}
// @Router       /orders [get]
func (h *OrderHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))

	items, err := h.service.GetAll(r.Context(), page, limit)
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get order by ID
// @Description  Mengembalikan satu order berdasarkan ID
// @Tags         Orders
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.Order
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /orders/{id} [get]
func (h *OrderHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
