import { describe, expect, it } from "vitest";
import { KodeGalatValues } from "../api-types";
import {
  ApiError,
  PESAN_GALAT,
  pesanGalat,
  pesanUntukKode,
  pesanUntukStatus,
} from "./errors";

describe("pesan galat standar (Indonesia)", () => {
  it("memetakan setiap KodeGalat ke pesan tak-kosong", () => {
    for (const code of KodeGalatValues) {
      expect(PESAN_GALAT[code]).toBeTypeOf("string");
      expect(PESAN_GALAT[code].length).toBeGreaterThan(0);
    }
  });

  it("jatuh kembali ke INTERNAL untuk kode tak dikenal", () => {
    expect(pesanUntukKode(undefined)).toBe(PESAN_GALAT.INTERNAL);
    expect(pesanUntukKode(null)).toBe(PESAN_GALAT.INTERNAL);
  });

  it("memetakan status HTTP umum", () => {
    expect(pesanUntukStatus(401)).toContain("Masuk kembali");
    expect(pesanUntukStatus(404)).toContain("Tidak ditemukan");
    expect(pesanUntukStatus(500)).toBe(PESAN_GALAT.INTERNAL);
  });

  it("pesanGalat membuka ApiError dan Error", () => {
    expect(pesanGalat(new ApiError(403, "khusus"))).toBe("khusus");
    expect(pesanGalat(new Error("boom"))).toBe("boom");
    expect(pesanGalat(undefined)).toBe(PESAN_GALAT.INTERNAL);
  });
});
