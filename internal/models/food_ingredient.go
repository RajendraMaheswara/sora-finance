package models

import (
	"time"

	"github.com/google/uuid"
)

type FoodIngredient struct {
	ID            uuid.UUID  `json:"id"`
	StoreID       uuid.UUID  `json:"m_store_id"`
	FoodUnitID    uuid.UUID  `json:"m_food_unit_id"`
	Code          string     `json:"code"`
	DeletedNote   *string    `json:"deleted_note,omitempty"`
	DeletedReason *string    `json:"deleted_reason,omitempty"`
	Name          string     `json:"name"`
	Note          *string    `json:"note,omitempty"`
	StockLimit    *float64   `json:"stock_limit,omitempty"`
	UnitPrice     *float64   `json:"unit_price,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
	CreatedBy     uuid.UUID  `json:"created_by"`
	UpdatedAt     *time.Time `json:"updated_at,omitempty"`
	UpdatedBy     *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt     *time.Time `json:"deleted_at,omitempty"`
	DeletedBy     *uuid.UUID `json:"deleted_by,omitempty"`
}
