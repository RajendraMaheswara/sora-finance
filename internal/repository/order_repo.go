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

func (r *OrderRepository) GetAll(ctx context.Context) ([]models.Order, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_customer_id, m_table_id, m_store_payment_method_id,
		       m_menu_online_order_type_id, m_store_regulation_ids, m_order_status_id,
		       m_order_payment_status_id, m_cashier_id, order_number, cancelled_reason,
		       cancelled_note, customer_name, customer_phone, deleted_reason, deleted_note,
		       total_item_price, total_regulation, sub_total, total_admin_debit_fee,
		       total_admin_ewallet_fee, rounding_price, total_paid, total_return, total_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by,
		       cancelled_at, cancelled_by
		FROM t_orders
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var orders []models.Order
	for rows.Next() {
		var o models.Order
		err := rows.Scan(
			&o.ID, &o.StoreID, &o.CustomerID, &o.TableID, &o.StorePaymentMethodID,
			&o.MenuOnlineOrderTypeID, &o.StoreRegulationIDs, &o.OrderStatusID,
			&o.OrderPaymentStatusID, &o.CashierID, &o.OrderNumber, &o.CancelledReason,
			&o.CancelledNote, &o.CustomerName, &o.CustomerPhone, &o.DeletedReason, &o.DeletedNote,
			&o.TotalItemPrice, &o.TotalRegulation, &o.SubTotal, &o.TotalAdminDebitFee,
			&o.TotalAdminEwalletFee, &o.RoundingPrice, &o.TotalPaid, &o.TotalReturn, &o.TotalPrice,
			&o.CreatedAt, &o.CreatedBy, &o.UpdatedAt, &o.UpdatedBy, &o.DeletedAt, &o.DeletedBy,
			&o.CancelledAt, &o.CancelledBy,
		)
		if err != nil {
			return nil, err
		}
		orders = append(orders, o)
	}
	return orders, nil
}

func (r *OrderRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Order, error) {
	var o models.Order
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_customer_id, m_table_id, m_store_payment_method_id,
		       m_menu_online_order_type_id, m_store_regulation_ids, m_order_status_id,
		       m_order_payment_status_id, m_cashier_id, order_number, cancelled_reason,
		       cancelled_note, customer_name, customer_phone, deleted_reason, deleted_note,
		       total_item_price, total_regulation, sub_total, total_admin_debit_fee,
		       total_admin_ewallet_fee, rounding_price, total_paid, total_return, total_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by,
		       cancelled_at, cancelled_by
		FROM t_orders
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&o.ID, &o.StoreID, &o.CustomerID, &o.TableID, &o.StorePaymentMethodID,
		&o.MenuOnlineOrderTypeID, &o.StoreRegulationIDs, &o.OrderStatusID,
		&o.OrderPaymentStatusID, &o.CashierID, &o.OrderNumber, &o.CancelledReason,
		&o.CancelledNote, &o.CustomerName, &o.CustomerPhone, &o.DeletedReason, &o.DeletedNote,
		&o.TotalItemPrice, &o.TotalRegulation, &o.SubTotal, &o.TotalAdminDebitFee,
		&o.TotalAdminEwalletFee, &o.RoundingPrice, &o.TotalPaid, &o.TotalReturn, &o.TotalPrice,
		&o.CreatedAt, &o.CreatedBy, &o.UpdatedAt, &o.UpdatedBy, &o.DeletedAt, &o.DeletedBy,
		&o.CancelledAt, &o.CancelledBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &o, nil
}