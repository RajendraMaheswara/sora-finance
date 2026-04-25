package models

import (
	"time"

	"github.com/google/uuid"
)

type SalesDailySummary struct {
	ID               uuid.UUID  `json:"id"`
	StoreID          uuid.UUID  `json:"m_store_id"`
	Date             time.Time  `json:"date"`
	TotalOmzet       *float64   `json:"total_omzet,omitempty"`
	TotalHpp         *float64   `json:"total_hpp,omitempty"`
	TotalProfit      *float64   `json:"total_profit,omitempty"`
	TotalDiscount    *float64   `json:"total_discount,omitempty"`
	TotalRegulation  *float64   `json:"total_regulation,omitempty"`
	TotalTransaction *float64   `json:"total_transaction,omitempty"`
	TotalRounding    *float64   `json:"total_rounding,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	CreatedBy        uuid.UUID  `json:"created_by"`
	UpdatedAt        *time.Time `json:"updated_at,omitempty"`
	UpdatedBy        *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt        *time.Time `json:"deleted_at,omitempty"`
	DeletedBy        *uuid.UUID `json:"deleted_by,omitempty"`
}
