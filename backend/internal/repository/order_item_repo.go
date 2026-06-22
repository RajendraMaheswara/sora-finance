package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type OrderItemRepository struct {
	db *pgxpool.Pool
}

func NewOrderItemRepository(db *pgxpool.Pool) *OrderItemRepository {
	return &OrderItemRepository{db: db}
}

func (r *OrderItemRepository) GetAll(ctx context.Context) ([]models.OrderItem, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, t_order_id, m_customer_id, m_menu_id, m_menu_variant_id, m_menu_packaging_id,
		       m_menu_offer_id, m_menu_online_order_id, m_store_discount_id, is_ready, menu_name, menu_offer_name,
		       menu_online_order_name, menu_packaging_name, menu_variant_name, menu_cogs, menu_price,
		       menu_offer_cogs, menu_offer_price, menu_online_order_price, menu_packaging_cogs, menu_packaging_price,
		       menu_variant_cogs, menu_variant_price, qty, store_discount_name, store_discount_price,
		       manual_discount_name, manual_discount_nominal, manual_discount_is_percentage, total_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by, m_order_type_id, note,
		       menu_category_name, order_type_name
		FROM t_order_items
		WHERE deleted_at IS NULL`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += `
		ORDER BY created_at DESC`
	rows, err := r.db.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.OrderItem
	for rows.Next() {
		var item models.OrderItem
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.OrderID, &item.CustomerID, &item.MenuID, &item.MenuVariantID,
			&item.MenuPackagingID, &item.MenuOfferID, &item.MenuOnlineOrderID, &item.StoreDiscountID,
			&item.IsReady, &item.MenuName, &item.MenuOfferName, &item.MenuOnlineOrderName, &item.MenuPackagingName,
			&item.MenuVariantName, &item.MenuCogs, &item.MenuPrice, &item.MenuOfferCogs, &item.MenuOfferPrice,
			&item.MenuOnlineOrderPrice, &item.MenuPackagingCogs, &item.MenuPackagingPrice, &item.MenuVariantCogs,
			&item.MenuVariantPrice, &item.Qty, &item.StoreDiscountName, &item.StoreDiscountPrice,
			&item.ManualDiscountName, &item.ManualDiscountNominal, &item.ManualDiscountIsPercentage, &item.TotalPrice,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
			&item.OrderTypeID, &item.Note, &item.MenuCategoryName, &item.OrderTypeName,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *OrderItemRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.OrderItem, error) {
	var item models.OrderItem
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, t_order_id, m_customer_id, m_menu_id, m_menu_variant_id, m_menu_packaging_id,
		       m_menu_offer_id, m_menu_online_order_id, m_store_discount_id, is_ready, menu_name, menu_offer_name,
		       menu_online_order_name, menu_packaging_name, menu_variant_name, menu_cogs, menu_price,
		       menu_offer_cogs, menu_offer_price, menu_online_order_price, menu_packaging_cogs, menu_packaging_price,
		       menu_variant_cogs, menu_variant_price, qty, store_discount_name, store_discount_price,
		       manual_discount_name, manual_discount_nominal, manual_discount_is_percentage, total_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by, m_order_type_id, note,
		       menu_category_name, order_type_name
		FROM t_order_items
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.OrderID, &item.CustomerID, &item.MenuID, &item.MenuVariantID,
		&item.MenuPackagingID, &item.MenuOfferID, &item.MenuOnlineOrderID, &item.StoreDiscountID,
		&item.IsReady, &item.MenuName, &item.MenuOfferName, &item.MenuOnlineOrderName, &item.MenuPackagingName,
		&item.MenuVariantName, &item.MenuCogs, &item.MenuPrice, &item.MenuOfferCogs, &item.MenuOfferPrice,
		&item.MenuOnlineOrderPrice, &item.MenuPackagingCogs, &item.MenuPackagingPrice, &item.MenuVariantCogs,
		&item.MenuVariantPrice, &item.Qty, &item.StoreDiscountName, &item.StoreDiscountPrice,
		&item.ManualDiscountName, &item.ManualDiscountNominal, &item.ManualDiscountIsPercentage, &item.TotalPrice,
		&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		&item.OrderTypeID, &item.Note, &item.MenuCategoryName, &item.OrderTypeName,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
