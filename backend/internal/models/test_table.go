package models

type TestTable struct {
	ID        int64   `json:"id"`
	NamaToko  *string `json:"nama_toko,omitempty"`
	NomorToko *int16  `json:"nomor_toko,omitempty"`
}
