"""
relatorio.py
------------
Consulta o histórico da frota gravado em SQLite (ver `historico.py`) e imprime
um relatório consolidado no terminal.

Uso:
    python relatorio.py                    # relatório do banco padrão
    python relatorio.py --db outro.db      # aponta para outro banco
    python relatorio.py --entregador ENT-001
    python relatorio.py --export-csv saida.csv
"""

import argparse
import csv
import os
import sqlite3
import sys

import config


def _conectar(caminho: str) -> sqlite3.Connection:
    if not os.path.exists(caminho):
        sys.exit(f"Banco '{caminho}' não encontrado. "
                 f"Rode a central para gerar histórico primeiro.")
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn


def _uma(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchone()


def relatorio(conn, filtro_ent: str = None) -> None:
    onde = "WHERE entregador = ?" if filtro_ent else ""
    args = (filtro_ent,) if filtro_ent else ()

    total = _uma(conn, f"SELECT COUNT(*) c FROM eventos {onde}", args)["c"]
    if total == 0:
        print("Nenhum evento registrado ainda.")
        return

    periodo = _uma(conn, f"SELECT MIN(timestamp) ini, MAX(timestamp) fim "
                         f"FROM eventos {onde}", args)
    n_ent = _uma(conn, f"SELECT COUNT(DISTINCT entregador) c "
                       f"FROM eventos {onde}", args)["c"]

    print("=" * 60)
    print(" RELATÓRIO DE HISTÓRICO DA FROTA")
    print("=" * 60)
    print(f" Banco       : {config.ARQUIVO_DB if not filtro_ent else '(filtro)'}")
    print(f" Eventos     : {total}")
    print(f" Entregadores: {n_ent}")
    print(f" Período     : {periodo['ini']}  →  {periodo['fim']}")
    print("-" * 60)

    # Eventos por tipo
    print(" Eventos por tipo:")
    for row in conn.execute(
            f"SELECT tipo, COUNT(*) c FROM eventos {onde} "
            f"GROUP BY tipo ORDER BY c DESC", args):
        print(f"   {row['tipo']:<14} {row['c']}")
    print("-" * 60)

    # Entregas concluídas e quedas inesperadas
    concluidas = _uma(conn,
        f"SELECT COUNT(*) c FROM eventos WHERE tipo='status' "
        f"AND resumo IN ('entregue','finalizado')"
        + (f" AND entregador='{filtro_ent}'" if filtro_ent else ""))["c"]
    quedas = _uma(conn,
        f"SELECT COUNT(*) c FROM eventos WHERE tipo='status' "
        f"AND resumo='offline_inesperado'"
        + (f" AND entregador='{filtro_ent}'" if filtro_ent else ""))["c"]
    print(f" Entregas concluídas : {concluidas}")
    print(f" Quedas inesperadas  : {quedas}")
    print("-" * 60)

    # Último status conhecido por entregador. Usa MAX(id) (e não MAX(timestamp))
    # para resolver corretamente empates de timestamp no mesmo segundo.
    print(" Último status por entregador:")
    filtro_status = "AND entregador = ?" if filtro_ent else ""
    for row in conn.execute(
            f"SELECT e.entregador, e.resumo, e.timestamp ts FROM eventos e "
            f"JOIN (SELECT entregador, MAX(id) mid FROM eventos "
            f"      WHERE tipo='status' {filtro_status} "
            f"      GROUP BY entregador) m ON e.id = m.mid "
            f"ORDER BY e.entregador", args):
        print(f"   {row['entregador']:<12} {row['resumo']:<20} {row['ts']}")
    print("=" * 60)


def exportar_csv(conn, caminho: str) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["timestamp", "entregador", "tipo", "resumo", "payload"])
        for row in conn.execute(
                "SELECT timestamp, entregador, tipo, resumo, payload "
                "FROM eventos ORDER BY id"):
            escritor.writerow(list(row))
    print(f"Exportado para {caminho}")


def main():
    parser = argparse.ArgumentParser(description="Relatório do histórico da frota")
    parser.add_argument("--db", default=config.ARQUIVO_DB,
                        help="Caminho do banco SQLite")
    parser.add_argument("--entregador", default=None,
                        help="Filtra por um entregador específico")
    parser.add_argument("--export-csv", default=None, metavar="ARQUIVO",
                        help="Exporta todos os eventos para um CSV e sai")
    args = parser.parse_args()

    # No console do Windows (cp1252) caracteres como "→" quebram a saída;
    # força UTF-8 quando possível.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    conn = _conectar(args.db)
    try:
        if args.export_csv:
            exportar_csv(conn, args.export_csv)
        else:
            relatorio(conn, args.entregador)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
