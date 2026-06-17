package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type OrderRepository struct {
	db *pgxpool.Pool
}

func NewOrderRepository(db *pgxpool.Pool) *OrderRepository {
	return &OrderRepository{db: db}
}

func (r *OrderRepository) GetAll(ctx context.Context, page, limit int) ([]models.Order, error) {
	if page < 1 {
		page = 1
	}
	if limit < 1 {
		limit = 100
	}
	offset := (page - 1) * limit

	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_customer_id, m_table_id, m_store_payment_method_id, m_menu_online_order_type_id,
		       m_store_regulation_ids, m_order_status_id, m_order_payment_status_id, m_cashier_id, order_number,
		       cancelled_reason, cancelled_note, customer_name, customer_phone, deleted_reason, deleted_note,
		       total_item_price, total_regulation, sub_total, total_admin_debit_fee, total_admin_ewallet_fee,
		       rounding_price, total_paid, total_return, total_price, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by, cancelled_at, cancelled_by, table_name, payment_method_name, cashier_name
		FROM t_orders
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2
	`, limit, offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.Order
	for rows.Next() {
		var item models.Order
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.CustomerID, &item.TableID, &item.StorePaymentMethodID,
			&item.MenuOnlineOrderTypeID, &item.StoreRegulationIDs, &item.OrderStatusID, &item.OrderPaymentStatusID,
			&item.CashierID, &item.OrderNumber, &item.CancelledReason, &item.CancelledNote, &item.CustomerName,
			&item.CustomerPhone, &item.DeletedReason, &item.DeletedNote, &item.TotalItemPrice,
			&item.TotalRegulation, &item.SubTotal, &item.TotalAdminDebitFee, &item.TotalAdminEwalletFee,
			&item.RoundingPrice, &item.TotalPaid, &item.TotalReturn, &item.TotalPrice, &item.CreatedAt,
			&item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
			&item.CancelledAt, &item.CancelledBy, &item.TableName, &item.PaymentMethodName, &item.CashierName,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *OrderRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Order, error) {
	var item models.Order
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_customer_id, m_table_id, m_store_payment_method_id, m_menu_online_order_type_id,
		       m_store_regulation_ids, m_order_status_id, m_order_payment_status_id, m_cashier_id, order_number,
		       cancelled_reason, cancelled_note, customer_name, customer_phone, deleted_reason, deleted_note,
		       total_item_price, total_regulation, sub_total, total_admin_debit_fee, total_admin_ewallet_fee,
		       rounding_price, total_paid, total_return, total_price, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by, cancelled_at, cancelled_by, table_name, payment_method_name, cashier_name
		FROM t_orders
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.CustomerID, &item.TableID, &item.StorePaymentMethodID,
		&item.MenuOnlineOrderTypeID, &item.StoreRegulationIDs, &item.OrderStatusID, &item.OrderPaymentStatusID,
		&item.CashierID, &item.OrderNumber, &item.CancelledReason, &item.CancelledNote, &item.CustomerName,
		&item.CustomerPhone, &item.DeletedReason, &item.DeletedNote, &item.TotalItemPrice,
		&item.TotalRegulation, &item.SubTotal, &item.TotalAdminDebitFee, &item.TotalAdminEwalletFee,
		&item.RoundingPrice, &item.TotalPaid, &item.TotalReturn, &item.TotalPrice, &item.CreatedAt,
		&item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		&item.CancelledAt, &item.CancelledBy, &item.TableName, &item.PaymentMethodName, &item.CashierName,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
