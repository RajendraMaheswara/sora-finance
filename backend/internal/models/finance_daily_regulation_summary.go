package models

import (
	"time"

	"github.com/google/uuid"
)

type FinanceDailyRegulationSummary struct {
	ID                    uuid.UUID  `json:"id"`
	StoreID               uuid.UUID  `json:"m_store_id"`
	FinanceDailySummaryID uuid.UUID  `json:"t_finance_daily_summary_id"`
	StoreRegulationID     *uuid.UUID `json:"m_store_regulation_id,omitempty"`
	Name                  string     `json:"name"`
	TotalRegulation       *float64   `json:"total_regulation,omitempty"`
	CreatedAt             time.Time  `json:"created_at"`
	CreatedBy             uuid.UUID  `json:"created_by"`
	UpdatedAt             *time.Time `json:"updated_at,omitempty"`
	UpdatedBy             *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt             *time.Time `json:"deleted_at,omitempty"`
	DeletedBy             *uuid.UUID `json:"deleted_by,omitempty"`
}
