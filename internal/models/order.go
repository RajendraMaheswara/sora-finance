package models

import (
	"time"

	"github.com/google/uuid"
)

type Order struct {
	ID                    uuid.UUID   `json:"id"`
	StoreID               uuid.UUID   `json:"m_store_id"`
	CustomerID            *uuid.UUID  `json:"m_customer_id,omitempty"`
	TableID               *uuid.UUID  `json:"m_table_id,omitempty"`
	StorePaymentMethodID  *uuid.UUID  `json:"m_store_payment_method_id,omitempty"`
	MenuOnlineOrderTypeID *int64      `json:"m_menu_online_order_type_id,omitempty"`
	StoreRegulationIDs    []uuid.UUID `json:"m_store_regulation_ids,omitempty"`
	OrderStatusID         int64       `json:"m_order_status_id"`
	OrderPaymentStatusID  int64       `json:"m_order_payment_status_id"`
	CashierID             *uuid.UUID  `json:"m_cashier_id,omitempty"`
	OrderNumber           string      `json:"order_number"`
	CancelledReason       *string     `json:"cancelled_reason,omitempty"`
	CancelledNote         *string     `json:"cancelled_note,omitempty"`
	CustomerName          *string     `json:"customer_name,omitempty"`
	CustomerPhone         *string     `json:"customer_phone,omitempty"`
	DeletedReason         *string     `json:"deleted_reason,omitempty"`
	DeletedNote           *string     `json:"deleted_note,omitempty"`
	TotalItemPrice        *float64    `json:"total_item_price,omitempty"`
	TotalRegulation       *float64    `json:"total_regulation,omitempty"`
	SubTotal              *float64    `json:"sub_total,omitempty"`
	TotalAdminDebitFee    *float64    `json:"total_admin_debit_fee,omitempty"`
	TotalAdminEwalletFee  *float64    `json:"total_admin_ewallet_fee,omitempty"`
	RoundingPrice         *float64    `json:"rounding_price,omitempty"`
	TotalPaid             *float64    `json:"total_paid,omitempty"`
	TotalReturn           *float64    `json:"total_return,omitempty"`
	TotalPrice            *float64    `json:"total_price,omitempty"`
	CreatedAt             time.Time   `json:"created_at"`
	CreatedBy             uuid.UUID   `json:"created_by"`
	UpdatedAt             *time.Time  `json:"updated_at,omitempty"`
	UpdatedBy             *uuid.UUID  `json:"updated_by,omitempty"`
	DeletedAt             *time.Time  `json:"deleted_at,omitempty"`
	DeletedBy             *uuid.UUID  `json:"deleted_by,omitempty"`
	CancelledAt           *time.Time  `json:"cancelled_at,omitempty"`
	CancelledBy           *uuid.UUID  `json:"cancelled_by,omitempty"`
}
