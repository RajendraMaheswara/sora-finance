package models

import (
	"time"

	"github.com/google/uuid"
)

type OrderItem struct {
	ID                         uuid.UUID  `json:"id"`
	StoreID                    uuid.UUID  `json:"m_store_id"`
	OrderID                    uuid.UUID  `json:"t_order_id"`
	CustomerID                 *uuid.UUID `json:"m_customer_id,omitempty"`
	MenuID                     *uuid.UUID `json:"m_menu_id,omitempty"`
	MenuVariantID              *uuid.UUID `json:"m_menu_variant_id,omitempty"`
	MenuPackagingID            *uuid.UUID `json:"m_menu_packaging_id,omitempty"`
	MenuOfferID                *uuid.UUID `json:"m_menu_offer_id,omitempty"`
	MenuOnlineOrderID          *uuid.UUID `json:"m_menu_online_order_id,omitempty"`
	StoreDiscountID            *uuid.UUID `json:"m_store_discount_id,omitempty"`
	IsReady                    bool       `json:"is_ready"`
	MenuName                   *string    `json:"menu_name,omitempty"`
	MenuOfferName              *string    `json:"menu_offer_name,omitempty"`
	MenuOnlineOrderName        *string    `json:"menu_online_order_name,omitempty"`
	MenuPackagingName          *string    `json:"menu_packaging_name,omitempty"`
	MenuVariantName            *string    `json:"menu_variant_name,omitempty"`
	MenuCogs                   *float64   `json:"menu_cogs,omitempty"`
	MenuPrice                  *float64   `json:"menu_price,omitempty"`
	MenuOfferCogs              *float64   `json:"menu_offer_cogs,omitempty"`
	MenuOfferPrice             *float64   `json:"menu_offer_price,omitempty"`
	MenuOnlineOrderPrice       *float64   `json:"menu_online_order_price,omitempty"`
	MenuPackagingCogs          *float64   `json:"menu_packaging_cogs,omitempty"`
	MenuPackagingPrice         *float64   `json:"menu_packaging_price,omitempty"`
	MenuVariantCogs            *float64   `json:"menu_variant_cogs,omitempty"`
	MenuVariantPrice           *float64   `json:"menu_variant_price,omitempty"`
	Qty                        *float64   `json:"qty,omitempty"`
	StoreDiscountName          *string    `json:"store_discount_name,omitempty"`
	StoreDiscountPrice         *float64   `json:"store_discount_price,omitempty"`
	ManualDiscountName         *string    `json:"manual_discount_name,omitempty"`
	ManualDiscountNominal      *float64   `json:"manual_discount_nominal,omitempty"`
	ManualDiscountIsPercentage *bool      `json:"manual_discount_is_percentage,omitempty"`
	TotalPrice                 *float64   `json:"total_price,omitempty"`
	CreatedAt                  time.Time  `json:"created_at"`
	CreatedBy                  uuid.UUID  `json:"created_by"`
	UpdatedAt                  *time.Time `json:"updated_at,omitempty"`
	UpdatedBy                  *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt                  *time.Time `json:"deleted_at,omitempty"`
	DeletedBy                  *uuid.UUID `json:"deleted_by,omitempty"`
	OrderTypeID                *int64     `json:"m_order_type_id,omitempty"`
	Note                       *string    `json:"note,omitempty"`
	MenuCategoryName           string     `json:"menu_category_name"`
	OrderTypeName              string     `json:"order_type_name"`
}
