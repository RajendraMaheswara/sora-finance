package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type SalesMenuSummaryRepository struct {
	db *pgxpool.Pool
}

func NewSalesMenuSummaryRepository(db *pgxpool.Pool) *SalesMenuSummaryRepository {
	return &SalesMenuSummaryRepository{db: db}
}

func (r *SalesMenuSummaryRepository) GetAll(ctx context.Context) ([]models.SalesMenuSummary, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_menu_id, m_menu_variant_id, m_menu_packaging_id, m_menu_offer_id,
		       m_menu_online_order_id, date, menu_name, menu_offer_name, menu_online_order_name,
		       menu_packaging_name, menu_variant_name, qty, total_menu_price, total_menu_offer_price,
		       total_menu_online_order_price, total_menu_packaging_price, total_menu_variant_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_sales_menu_summaries
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.SalesMenuSummary
	for rows.Next() {
		var item models.SalesMenuSummary
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.MenuID, &item.MenuVariantID, &item.MenuPackagingID, &item.MenuOfferID,
			&item.MenuOnlineOrderID, &item.Date, &item.MenuName, &item.MenuOfferName, &item.MenuOnlineOrderName,
			&item.MenuPackagingName, &item.MenuVariantName, &item.Qty, &item.TotalMenuPrice,
			&item.TotalMenuOfferPrice, &item.TotalMenuOnlineOrderPrice, &item.TotalMenuPackagingPrice,
			&item.TotalMenuVariantPrice, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
			&item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *SalesMenuSummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.SalesMenuSummary, error) {
	var item models.SalesMenuSummary
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_menu_id, m_menu_variant_id, m_menu_packaging_id, m_menu_offer_id,
		       m_menu_online_order_id, date, menu_name, menu_offer_name, menu_online_order_name,
		       menu_packaging_name, menu_variant_name, qty, total_menu_price, total_menu_offer_price,
		       total_menu_online_order_price, total_menu_packaging_price, total_menu_variant_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_sales_menu_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.MenuID, &item.MenuVariantID, &item.MenuPackagingID, &item.MenuOfferID,
		&item.MenuOnlineOrderID, &item.Date, &item.MenuName, &item.MenuOfferName, &item.MenuOnlineOrderName,
		&item.MenuPackagingName, &item.MenuVariantName, &item.Qty, &item.TotalMenuPrice,
		&item.TotalMenuOfferPrice, &item.TotalMenuOnlineOrderPrice, &item.TotalMenuPackagingPrice,
		&item.TotalMenuVariantPrice, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
		&item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
