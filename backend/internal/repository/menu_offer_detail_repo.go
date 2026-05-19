package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type MenuOfferDetailRepository struct {
	db *pgxpool.Pool
}

func NewMenuOfferDetailRepository(db *pgxpool.Pool) *MenuOfferDetailRepository {
	return &MenuOfferDetailRepository{db: db}
}

func (r *MenuOfferDetailRepository) GetAll(ctx context.Context) ([]models.MenuOfferDetail, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_menu_offer_id, m_menu_id, m_menu_variant_id, m_menu_packaging_id, qty,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_offer_details
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.MenuOfferDetail
	for rows.Next() {
		var item models.MenuOfferDetail
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.MenuOfferID, &item.MenuID, &item.MenuVariantID, &item.MenuPackagingID,
			&item.Qty, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuOfferDetailRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MenuOfferDetail, error) {
	var item models.MenuOfferDetail
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_menu_offer_id, m_menu_id, m_menu_variant_id, m_menu_packaging_id, qty,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_offer_details
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.MenuOfferID, &item.MenuID, &item.MenuVariantID, &item.MenuPackagingID,
		&item.Qty, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
