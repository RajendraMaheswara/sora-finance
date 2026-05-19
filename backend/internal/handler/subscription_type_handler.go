package handler

import (
	"net/http"
	"sora-finance-api/internal/service"
	"strconv"

	"github.com/go-chi/chi/v5"
)

type SubscriptionTypeHandler struct {
	service *service.SubscriptionTypeService
}

func NewSubscriptionTypeHandler(service *service.SubscriptionTypeService) *SubscriptionTypeHandler {
	return &SubscriptionTypeHandler{service: service}
}

// GetAll godoc
// @Summary      Get all subscription types
// @Description  Mengembalikan daftar semua subscription types
// @Tags         SubscriptionTypes
// @Produce      json
// @Success      200  {array}  models.SubscriptionType
// @Failure      500  {object}  map[string]interface{}
// @Router       /subscription-types [get]
func (h *SubscriptionTypeHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get subscription type by ID
// @Description  Mengembalikan satu subscription type berdasarkan ID
// @Tags         SubscriptionTypes
// @Produce      json
// @Param        id   path      int  true  "ID"
// @Success      200  {object}  models.SubscriptionType
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /subscription-types/{id} [get]
func (h *SubscriptionTypeHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		http.Error(w, "invalid id", http.StatusBadRequest)
		return
	}
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
