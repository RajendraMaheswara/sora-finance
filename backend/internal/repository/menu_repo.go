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

type MenuRepository struct {
	db *pgxpool.Pool
}

func NewMenuRepository(db *pgxpool.Pool) *MenuRepository {
	return &MenuRepository{db: db}
}

func (r *MenuRepository) GetAll(ctx context.Context) ([]models.Menu, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_menu_category_id, m_store_regulation_id, background_color, cogs, code,
		       description, image_url, name, price, total_stock, created_at, created_by, updated_at,
		       updated_by, deleted_at, deleted_by
		FROM m_menus
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

	var items []models.Menu
	for rows.Next() {
		var item models.Menu
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.MenuCategoryID, &item.StoreRegulationID, &item.BackgroundColor,
			&item.Cogs, &item.Code, &item.Description, &item.ImageURL, &item.Name, &item.Price,
			&item.TotalStock, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
			&item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Menu, error) {
	var item models.Menu
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_menu_category_id, m_store_regulation_id, background_color, cogs, code,
		       description, image_url, name, price, total_stock, created_at, created_by, updated_at,
		       updated_by, deleted_at, deleted_by
		FROM m_menus
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.MenuCategoryID, &item.StoreRegulationID, &item.BackgroundColor,
		&item.Cogs, &item.Code, &item.Description, &item.ImageURL, &item.Name, &item.Price,
		&item.TotalStock, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
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
