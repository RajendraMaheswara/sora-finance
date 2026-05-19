package models

import (
	"time"

	"github.com/google/uuid"
)

type MenuOnlineOrder struct {
	ID                    uuid.UUID  `json:"id"`
	StoreID               uuid.UUID  `json:"m_store_id"`
	MenuOnlineOrderTypeID int64      `json:"m_menu_online_order_type_id"`
	MenuID                uuid.UUID  `json:"m_menu_id"`
	MenuPackagingID       uuid.UUID  `json:"m_menu_packaging_id"`
	IsPercentage          bool       `json:"is_percentage"`
	Name                  string     `json:"name"`
	Price                 *float64   `json:"price,omitempty"`
	CreatedAt             time.Time  `json:"created_at"`
	CreatedBy             uuid.UUID  `json:"created_by"`
	UpdatedAt             *time.Time `json:"updated_at,omitempty"`
	UpdatedBy             *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt             *time.Time `json:"deleted_at,omitempty"`
	DeletedBy             *uuid.UUID `json:"deleted_by,omitempty"`
}
