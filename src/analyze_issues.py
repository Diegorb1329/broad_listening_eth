import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime
import os
from pathlib import Path

class IssueAnalyzer:
    def __init__(self, db_path="github_issues.db"):
        """
        Inicializa el analizador de issues
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        self.conn = None
        
        # Crear directorio para guardar gráficos
        self.output_dir = Path("Analisis")
        self.output_dir.mkdir(exist_ok=True)
        
    def get_connection(self):
        """
        Obtiene una conexión a la base de datos
        
        Returns:
            Conexión SQLite
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def load_issues_to_dataframe(self):
        """
        Carga los issues en un DataFrame de pandas
        
        Returns:
            DataFrame con los issues
        """
        conn = self.get_connection()
        
        # Cargar issues
        df_issues = pd.read_sql_query("SELECT * FROM issues", conn)
        
        # Convertir fechas a datetime
        for date_col in ['created_at', 'updated_at', 'closed_at']:
            df_issues[date_col] = pd.to_datetime(df_issues[date_col])
            
        return df_issues
    
    def load_comments_to_dataframe(self):
        """
        Carga los comentarios en un DataFrame de pandas
        
        Returns:
            DataFrame con los comentarios
        """
        conn = self.get_connection()
        
        # Cargar comentarios
        df_comments = pd.read_sql_query("SELECT * FROM comments", conn)
        
        # Convertir fechas a datetime
        for date_col in ['created_at', 'updated_at']:
            df_comments[date_col] = pd.to_datetime(df_comments[date_col])
            
        return df_comments
    
    def analyze_top_labels(self, df_issues, top_n=15):
        """
        Analiza las etiquetas más comunes
        
        Args:
            df_issues: DataFrame con los issues
            top_n: Número de etiquetas principales a mostrar
        """
        # Expandir las etiquetas (están separadas por comas)
        all_labels = []
        for labels_str in df_issues['labels'].dropna():
            if labels_str:  # Asegurarse de que no sea vacío
                all_labels.extend(labels_str.split(','))
        
        # Contar etiquetas
        label_counts = pd.Series(all_labels).value_counts().nlargest(top_n)
        
        # Crear gráfico
        plt.figure(figsize=(12, 8))
        sns.barplot(x=label_counts.values, y=label_counts.index)
        plt.title(f'Top {top_n} etiquetas en issues abiertos', fontsize=16)
        plt.xlabel('Número de issues', fontsize=12)
        plt.ylabel('Etiqueta', fontsize=12)
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'top_labels.png', dpi=300)
        plt.close()
        
        return label_counts
    
    def analyze_comments_distribution(self, df_issues):
        """
        Analiza la distribución de comentarios por issue
        
        Args:
            df_issues: DataFrame con los issues
        """
        # Analizar distribución de comentarios
        plt.figure(figsize=(10, 6))
        sns.histplot(df_issues['comments_count'], kde=True, bins=30)
        plt.title('Distribución de comentarios por issue', fontsize=16)
        plt.xlabel('Número de comentarios', fontsize=12)
        plt.ylabel('Número de issues', fontsize=12)
        plt.xlim(0, df_issues['comments_count'].quantile(0.95))  # Limitar eje x al percentil 95
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'comments_distribution.png', dpi=300)
        plt.close()
        
        # Top issues con más comentarios
        top_commented = df_issues.nlargest(10, 'comments_count')[['number', 'title', 'comments_count']]
        
        # Crear gráfico para top issues con más comentarios
        plt.figure(figsize=(12, 8))
        sns.barplot(x='comments_count', y='number', data=top_commented)
        plt.title('Top 10 issues con más comentarios', fontsize=16)
        plt.xlabel('Número de comentarios', fontsize=12)
        plt.ylabel('Número de issue', fontsize=12)
        
        # Añadir etiquetas con títulos truncados
        for i, row in enumerate(top_commented.itertuples()):
            title = row.title if len(row.title) < 40 else row.title[:37] + '...'
            plt.text(row.comments_count + 0.5, i, title, va='center')
            
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'top_commented_issues.png', dpi=300)
        plt.close()
        
        return top_commented
    
    def analyze_issues_over_time(self, df_issues):
        """
        Analiza la creación de issues a lo largo del tiempo
        
        Args:
            df_issues: DataFrame con los issues
        """
        # Agrupar por mes
        df_issues['month'] = df_issues['created_at'].dt.to_period('M')
        monthly_counts = df_issues.groupby('month').size()
        monthly_df = monthly_counts.reset_index()
        monthly_df.columns = ['month', 'count']
        monthly_df['month'] = monthly_df['month'].dt.to_timestamp()
        
        # Crear gráfico
        plt.figure(figsize=(14, 6))
        plt.plot(monthly_df['month'], monthly_df['count'], marker='o', linestyle='-')
        plt.title('Issues abiertos creados por mes', fontsize=16)
        plt.xlabel('Fecha', fontsize=12)
        plt.ylabel('Número de issues', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'issues_over_time.png', dpi=300)
        plt.close()
        
        return monthly_df
    
    def analyze_top_contributors(self, df_issues, top_n=10):
        """
        Analiza los usuarios que más issues han creado
        
        Args:
            df_issues: DataFrame con los issues
            top_n: Número de contribuidores principales a mostrar
        """
        # Contar issues por usuario
        contributor_counts = df_issues['user_login'].value_counts().nlargest(top_n)
        
        # Crear gráfico
        plt.figure(figsize=(12, 8))
        sns.barplot(x=contributor_counts.values, y=contributor_counts.index)
        plt.title(f'Top {top_n} contribuidores por issues abiertos', fontsize=16)
        plt.xlabel('Número de issues', fontsize=12)
        plt.ylabel('Usuario', fontsize=12)
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'top_contributors.png', dpi=300)
        plt.close()
        
        return contributor_counts
    
    def analyze_reactions(self, df_issues):
        """
        Analiza las reacciones en los issues
        
        Args:
            df_issues: DataFrame con los issues
        """
        # Distribución de reacciones totales
        plt.figure(figsize=(10, 6))
        sns.histplot(df_issues['reactions_total_count'], kde=True, bins=30)
        plt.title('Distribución de reacciones por issue', fontsize=16)
        plt.xlabel('Número de reacciones', fontsize=12)
        plt.ylabel('Número de issues', fontsize=12)
        plt.xlim(0, df_issues['reactions_total_count'].quantile(0.95))
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'reactions_distribution.png', dpi=300)
        plt.close()
        
        # Top issues con más reacciones
        top_reactions = df_issues.nlargest(10, 'reactions_total_count')[['number', 'title', 'reactions_total_count']]
        
        # Crear gráfico para top issues con más reacciones
        plt.figure(figsize=(12, 8))
        sns.barplot(x='reactions_total_count', y='number', data=top_reactions)
        plt.title('Top 10 issues con más reacciones', fontsize=16)
        plt.xlabel('Número de reacciones', fontsize=12)
        plt.ylabel('Número de issue', fontsize=12)
        
        # Añadir etiquetas con títulos truncados
        for i, row in enumerate(top_reactions.itertuples()):
            title = row.title if len(row.title) < 40 else row.title[:37] + '...'
            plt.text(row.reactions_total_count + 0.5, i, title, va='center')
            
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'top_reacted_issues.png', dpi=300)
        plt.close()
        
        return top_reactions
    
    def analyze_issue_resolution_time(self, df_issues):
        """
        Analiza el tiempo de resolución de issues (para issues cerrados)
        
        Args:
            df_issues: DataFrame con los issues
        """
        # Filtrar issues cerrados
        closed_issues = df_issues[df_issues['closed_at'].notna()].copy()
        
        if len(closed_issues) == 0:
            print("No hay issues cerrados para analizar el tiempo de resolución")
            return None
        
        # Calcular tiempo de resolución en días
        closed_issues['resolution_days'] = (closed_issues['closed_at'] - closed_issues['created_at']).dt.days
        
        # Histograma de tiempos de resolución
        plt.figure(figsize=(10, 6))
        sns.histplot(closed_issues['resolution_days'], kde=True, bins=30)
        plt.title('Distribución de tiempos de resolución de issues', fontsize=16)
        plt.xlabel('Días hasta el cierre', fontsize=12)
        plt.ylabel('Número de issues', fontsize=12)
        plt.xlim(0, closed_issues['resolution_days'].quantile(0.95))
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'resolution_time.png', dpi=300)
        plt.close()
        
        return closed_issues
    
    def analyze_labels_correlation_with_comments(self, df_issues):
        """
        Analiza la correlación entre etiquetas y cantidad de comentarios
        
        Args:
            df_issues: DataFrame con los issues
        """
        # Obtener todas las etiquetas únicas
        all_unique_labels = set()
        for labels_str in df_issues['labels'].dropna():
            if labels_str:
                all_unique_labels.update(labels_str.split(','))
        
        # Crear columnas de etiquetas (one-hot encoding)
        label_data = []
        for index, row in df_issues.iterrows():
            labels_dict = {label: 0 for label in all_unique_labels}
            if pd.notna(row['labels']) and row['labels']:
                issue_labels = row['labels'].split(',')
                for label in issue_labels:
                    labels_dict[label] = 1
            labels_dict['issue_id'] = row['issue_id']
            labels_dict['comments_count'] = row['comments_count']
            label_data.append(labels_dict)
        
        # Crear DataFrame con el one-hot encoding
        df_labels = pd.DataFrame(label_data)
        
        # Calcular comentarios promedio por etiqueta
        label_stats = []
        for label in all_unique_labels:
            issues_with_label = df_labels[df_labels[label] == 1]
            if len(issues_with_label) > 0:
                avg_comments = issues_with_label['comments_count'].mean()
                count = len(issues_with_label)
                label_stats.append({
                    'label': label,
                    'avg_comments': avg_comments,
                    'count': count
                })
        
        # Convertir a DataFrame y ordenar
        df_label_stats = pd.DataFrame(label_stats)
        df_label_stats = df_label_stats.sort_values('avg_comments', ascending=False)
        
        # Filtrar etiquetas con al menos 5 issues para tener estadísticas significativas
        df_label_stats = df_label_stats[df_label_stats['count'] >= 5]
        
        # Tomar top 20
        top_n = min(20, len(df_label_stats))
        top_labels = df_label_stats.head(top_n)
        
        # Crear gráfico
        plt.figure(figsize=(12, 10))
        sns.barplot(x='avg_comments', y='label', data=top_labels)
        plt.title(f'Top {top_n} etiquetas por promedio de comentarios', fontsize=16)
        plt.xlabel('Promedio de comentarios', fontsize=12)
        plt.ylabel('Etiqueta', fontsize=12)
        
        # Añadir etiquetas con el número de issues
        for i, row in enumerate(top_labels.itertuples()):
            plt.text(row.avg_comments + 0.2, i, f"({row.count} issues)", va='center')
            
        plt.tight_layout()
        
        # Guardar gráfico
        plt.savefig(self.output_dir / 'labels_comments_correlation.png', dpi=300)
        plt.close()
        
        return df_label_stats
    
    def run_all_analyses(self):
        """
        Ejecuta todos los análisis y genera un informe
        """
        print("Cargando datos...")
        df_issues = self.load_issues_to_dataframe()
        df_comments = self.load_comments_to_dataframe()
        
        print(f"Analizando {len(df_issues)} issues y {len(df_comments)} comentarios...")
        
        # Resumen general
        open_count = len(df_issues[df_issues['state'] == 'open'])
        closed_count = len(df_issues[df_issues['state'] == 'closed'])
        total_comments = df_issues['comments_count'].sum()
        avg_comments = df_issues['comments_count'].mean()
        
        print("\n--- RESUMEN GENERAL ---")
        print(f"Total de issues: {len(df_issues)}")
        print(f"Issues abiertos: {open_count}")
        print(f"Issues cerrados: {closed_count}")
        print(f"Total de comentarios: {total_comments}")
        print(f"Promedio de comentarios por issue: {avg_comments:.2f}")
        
        # Ejecutar análisis
        print("\nGenerando gráficos...")
        self.analyze_top_labels(df_issues)
        self.analyze_comments_distribution(df_issues)
        self.analyze_issues_over_time(df_issues)
        self.analyze_top_contributors(df_issues)
        self.analyze_reactions(df_issues)
        self.analyze_issue_resolution_time(df_issues)
        self.analyze_labels_correlation_with_comments(df_issues)
        
        print(f"\nAnálisis completado. Los gráficos se han guardado en el directorio: {self.output_dir}")
        
    def close(self):
        """
        Cierra la conexión a la base de datos
        """
        if self.conn:
            self.conn.close()
            self.conn = None

def main():
    # Inicializar y ejecutar análisis
    analyzer = IssueAnalyzer()
    analyzer.run_all_analyses()
    analyzer.close()

if __name__ == "__main__":
    main() 