package models

import (
	"time"

	"github.com/google/uuid"
)

type IngredientStockHistory struct {
	ID                   uuid.UUID  `json:"id"`
	StoreID              uuid.UUID  `json:"m_store_id"`
	FoodIngredientID     uuid.UUID  `json:"m_food_ingredient_id"`
	Added                *float64   `json:"added,omitempty"`
	CurrentStock         *float64   `json:"current_stock,omitempty"`
	Date                 *time.Time `json:"date,omitempty"`
	DeletedNote          *string    `json:"deleted_note,omitempty"`
	DeletedReason        *string    `json:"deleted_reason,omitempty"`
	Journal              *float64   `json:"journal,omitempty"`
	Note                 *string    `json:"note,omitempty"`
	PreviousStock        *float64   `json:"previous_stock,omitempty"`
	Reduced              *float64   `json:"reduced,omitempty"`
	RemainingCapital     *float64   `json:"remaining_capital,omitempty"`
	Status               string     `json:"status"`
	StockChange          *float64   `json:"stock_change,omitempty"`
	TotalRemainingCapital *float64  `json:"total_remaining_capital,omitempty"`
	TotalUnitPrice       *float64   `json:"total_unit_price,omitempty"`
	Type                 string     `json:"type"`
	UnitPrice            *float64   `json:"unit_price,omitempty"`
	CreatedAt            time.Time  `json:"created_at"`
	CreatedBy            uuid.UUID  `json:"created_by"`
	UpdatedAt            *time.Time `json:"updated_at,omitempty"`
	UpdatedBy            *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt            *time.Time `json:"deleted_at,omitempty"`
	DeletedBy            *uuid.UUID `json:"deleted_by,omitempty"`
}