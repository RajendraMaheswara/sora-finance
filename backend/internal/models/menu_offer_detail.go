package models

import (
	"time"

	"github.com/google/uuid"
)

type MenuOfferDetail struct {
	ID              uuid.UUID  `json:"id"`
	StoreID         uuid.UUID  `json:"m_store_id"`
	MenuOfferID     uuid.UUID  `json:"m_menu_offer_id"`
	MenuID          uuid.UUID  `json:"m_menu_id"`
	MenuVariantID   *uuid.UUID `json:"m_menu_variant_id,omitempty"`
	MenuPackagingID *uuid.UUID `json:"m_menu_packaging_id,omitempty"`
	Qty             *float64   `json:"qty,omitempty"`
	CreatedAt       time.Time  `json:"created_at"`
	CreatedBy       uuid.UUID  `json:"created_by"`
	UpdatedAt       *time.Time `json:"updated_at,omitempty"`
	UpdatedBy       *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt       *time.Time `json:"deleted_at,omitempty"`
	DeletedBy       *uuid.UUID `json:"deleted_by,omitempty"`
}
