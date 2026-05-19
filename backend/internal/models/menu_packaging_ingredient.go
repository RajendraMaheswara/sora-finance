package models

import (
	"time"

	"github.com/google/uuid"
)

type MenuPackagingIngredient struct {
	ID               uuid.UUID  `json:"id"`
	StoreID          uuid.UUID  `json:"m_store_id"`
	MenuPackagingID  uuid.UUID  `json:"m_menu_packaging_id"`
	FoodIngredientID uuid.UUID  `json:"m_food_ingredient_id"`
	Qty              *float64   `json:"qty,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	CreatedBy        uuid.UUID  `json:"created_by"`
	UpdatedAt        *time.Time `json:"updated_at,omitempty"`
	UpdatedBy        *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt        *time.Time `json:"deleted_at,omitempty"`
	DeletedBy        *uuid.UUID `json:"deleted_by,omitempty"`
}
