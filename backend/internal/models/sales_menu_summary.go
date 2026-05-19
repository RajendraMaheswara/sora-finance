package models

import (
	"time"

	"github.com/google/uuid"
)

type SalesMenuSummary struct {
	ID                        uuid.UUID  `json:"id"`
	StoreID                   uuid.UUID  `json:"m_store_id"`
	MenuID                    *uuid.UUID `json:"m_menu_id,omitempty"`
	MenuVariantID             *uuid.UUID `json:"m_menu_variant_id,omitempty"`
	MenuPackagingID           *uuid.UUID `json:"m_menu_packaging_id,omitempty"`
	MenuOfferID               *uuid.UUID `json:"m_menu_offer_id,omitempty"`
	MenuOnlineOrderID         *uuid.UUID `json:"m_menu_online_order_id,omitempty"`
	Date                      time.Time  `json:"date"`
	MenuName                  string     `json:"menu_name"`
	MenuOfferName             *string    `json:"menu_offer_name,omitempty"`
	MenuOnlineOrderName       *string    `json:"menu_online_order_name,omitempty"`
	MenuPackagingName         *string    `json:"menu_packaging_name,omitempty"`
	MenuVariantName           *string    `json:"menu_variant_name,omitempty"`
	Qty                       *float64   `json:"qty,omitempty"`
	TotalMenuPrice            *float64   `json:"total_menu_price,omitempty"`
	TotalMenuOfferPrice       *float64   `json:"total_menu_offer_price,omitempty"`
	TotalMenuOnlineOrderPrice *float64   `json:"total_menu_online_order_price,omitempty"`
	TotalMenuPackagingPrice   *float64   `json:"total_menu_packaging_price,omitempty"`
	TotalMenuVariantPrice     *float64   `json:"total_menu_variant_price,omitempty"`
	CreatedAt                 time.Time  `json:"created_at"`
	CreatedBy                 uuid.UUID  `json:"created_by"`
	UpdatedAt                 *time.Time `json:"updated_at,omitempty"`
	UpdatedBy                 *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt                 *time.Time `json:"deleted_at,omitempty"`
	DeletedBy                 *uuid.UUID `json:"deleted_by,omitempty"`
}
