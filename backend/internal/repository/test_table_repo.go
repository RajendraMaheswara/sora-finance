package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type TestTableRepository struct {
	db *pgxpool.Pool
}

func NewTestTableRepository(db *pgxpool.Pool) *TestTableRepository {
	return &TestTableRepository{db: db}
}

func (r *TestTableRepository) GetAll(ctx context.Context) ([]models.TestTable, error) {
	rows, err := r.db.Query(ctx, `SELECT id, nama_toko, nomor_toko FROM public.test_table ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.TestTable
	for rows.Next() {
		var t models.TestTable
		err := rows.Scan(&t.ID, &t.NamaToko, &t.NomorToko)
		if err != nil {
			return nil, err
		}
		items = append(items, t)
	}
	return items, nil
}

func (r *TestTableRepository) GetByID(ctx context.Context, id int64) (*models.TestTable, error) {
	var t models.TestTable
	err := r.db.QueryRow(ctx, `SELECT id, nama_toko, nomor_toko FROM public.test_table WHERE id = $1`, id).
		Scan(&t.ID, &t.NamaToko, &t.NomorToko)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &t, nil
}
