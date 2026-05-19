package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type MenuOfferRepository struct {
	db *pgxpool.Pool
}

func NewMenuOfferRepository(db *pgxpool.Pool) *MenuOfferRepository {
	return &MenuOfferRepository{db: db}
}

func (r *MenuOfferRepository) GetAll(ctx context.Context) ([]models.MenuOffer, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_store_regulation_id, expired_offer_date, image_url, name, price,
		       start_offer_date, terms_and_conditions, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by, total_stock
		FROM m_menu_offers
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.MenuOffer
	for rows.Next() {
		var item models.MenuOffer
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.StoreRegulationID, &item.ExpiredOfferDate, &item.ImageURL, &item.Name,
			&item.Price, &item.StartOfferDate, &item.TermsAndConditions, &item.CreatedAt, &item.CreatedBy,
			&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy, &item.TotalStock,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuOfferRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MenuOffer, error) {
	var item models.MenuOffer
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_store_regulation_id, expired_offer_date, image_url, name, price,
		       start_offer_date, terms_and_conditions, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by, total_stock
		FROM m_menu_offers
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.StoreRegulationID, &item.ExpiredOfferDate, &item.ImageURL, &item.Name,
		&item.Price, &item.StartOfferDate, &item.TermsAndConditions, &item.CreatedAt, &item.CreatedBy,
		&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy, &item.TotalStock,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
