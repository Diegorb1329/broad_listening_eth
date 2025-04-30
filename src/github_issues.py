import requests
import json
import os
import argparse
import sqlite3
from datetime import datetime
import time
from pathlib import Path

class GitHubIssueExtractor:
    def __init__(self, owner, repo, token=None, db_path=None):
        self.owner = owner
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Si hay un token de GitHub disponible, úsalo para evitar límites de tasa
        if token:
            self.headers["Authorization"] = f"token {token}"
        elif "GITHUB_TOKEN" in os.environ:
            self.headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"
            
        # Crear directorio para guardar datos si no existe
        self.data_dir = Path("Data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Base de datos SQLite
        self.db_manager = None
        if db_path:
            self.db_manager = DatabaseManager(db_path)
            
    def get_issues(self, state="open", labels=None, per_page=100, max_pages=10):
        """
        Extrae issues del repositorio
        
        Args:
            state: Estado de los issues ('open', 'closed', 'all')
            labels: Lista de etiquetas para filtrar (opcional)
            per_page: Número de issues por página
            max_pages: Número máximo de páginas a extraer
        
        Returns:
            List of issues
        """
        all_issues = []
        page = 1
        
        while page <= max_pages:
            url = f"{self.base_url}/issues"
            params = {
                "state": state,
                "per_page": per_page,
                "page": page,
                "sort": "created",
                "direction": "desc"
            }
            
            # Agregar filtro de etiquetas si se proporciona
            if labels:
                params["labels"] = ",".join(labels)
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error al obtener issues: {response.status_code}")
                print(response.text)
                break
                
            issues = response.json()
            
            if not issues:
                break
                
            all_issues.extend(issues)
            print(f"Obtenidos {len(issues)} issues de la página {page}")
            
            # Verificar si hay más páginas
            if len(issues) < per_page:
                break
                
            page += 1
            
            # Respetar límites de tasa de la API
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            print(f"Consultas restantes: {remaining}")
            
            if remaining < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time.time(), 0) + 10
                print(f"Límite de tasa alcanzado. Esperando {sleep_time:.0f} segundos...")
                time.sleep(sleep_time)
        
        # Guardar issues en un archivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        labels_str = "_".join(labels) if labels else "all"
        with open(self.data_dir / f"issues_{state}_{labels_str}_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(all_issues, f, indent=2)
            
        # Guardar en la base de datos si está habilitada
        if self.db_manager:
            self.db_manager.save_issues(all_issues)
            
        return all_issues
    
    def get_issue_comments(self, issue_number):
        """
        Extrae comentarios de un issue específico
        
        Args:
            issue_number: Número del issue
            
        Returns:
            List of comments
        """
        url = f"{self.base_url}/issues/{issue_number}/comments"
        all_comments = []
        page = 1
        
        while True:
            params = {
                "per_page": 100,
                "page": page
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error al obtener comentarios para el issue #{issue_number}: {response.status_code}")
                print(response.text)
                break
                
            comments = response.json()
            
            if not comments:
                break
                
            all_comments.extend(comments)
            
            if len(comments) < 100:
                break
                
            page += 1
            
            # Respetar límites de tasa de la API
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            if remaining < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time.time(), 0) + 10
                print(f"Límite de tasa alcanzado. Esperando {sleep_time:.0f} segundos...")
                time.sleep(sleep_time)
        
        # Guardar comentarios en un archivo JSON
        with open(self.data_dir / f"comments_issue_{issue_number}.json", "w", encoding="utf-8") as f:
            json.dump(all_comments, f, indent=2)
            
        # Guardar en la base de datos si está habilitada
        if self.db_manager:
            self.db_manager.save_comments(all_comments)
            
        return all_comments
    
    def get_all_issues_with_comments(self, state="open", labels=None, max_issues=100):
        """
        Extrae issues y sus comentarios
        
        Args:
            state: Estado de los issues ('open', 'closed', 'all')
            labels: Lista de etiquetas para filtrar (opcional)
            max_issues: Número máximo de issues a procesar
            
        Returns:
            Dict mapping issue numbers to their comments
        """
        issues = self.get_issues(state=state, labels=labels, per_page=100, max_pages=(max_issues // 100) + 1)
        issues = issues[:max_issues]
        
        issue_comments = {}
        
        for idx, issue in enumerate(issues):
            issue_number = issue["number"]
            print(f"Obteniendo comentarios para el issue #{issue_number} ({idx+1}/{len(issues)})")
            
            comments = self.get_issue_comments(issue_number)
            issue_comments[issue_number] = comments
            
            # Pequeña pausa para no sobrecargar la API
            time.sleep(0.5)
        
        # Guardar toda la información en un archivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        labels_str = "_".join(labels) if labels else "all"
        with open(self.data_dir / f"issues_with_comments_{state}_{labels_str}_{timestamp}.json", "w", encoding="utf-8") as f:
            result = {"issues": issues, "comments": issue_comments}
            json.dump(result, f, indent=2)
            
        return issues, issue_comments
        
    def get_repository_labels(self):
        """
        Obtiene todas las etiquetas disponibles en el repositorio
        
        Returns:
            List of labels
        """
        url = f"{self.base_url}/labels"
        all_labels = []
        page = 1
        
        while True:
            params = {
                "per_page": 100,
                "page": page
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error al obtener etiquetas: {response.status_code}")
                print(response.text)
                break
                
            labels = response.json()
            
            if not labels:
                break
                
            all_labels.extend(labels)
            
            if len(labels) < 100:
                break
                
            page += 1
        
        # Guardar etiquetas en un archivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(self.data_dir / f"labels_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(all_labels, f, indent=2)
            
        return all_labels

class DatabaseManager:
    """
    Gestiona la conexión y operaciones con la base de datos SQLite
    para almacenar issues y comentarios
    """
    
    def __init__(self, db_path):
        """
        Inicializa el gestor de base de datos
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        self.conn = None
        self.initialize_db()
        
    def get_connection(self):
        """
        Obtiene una conexión a la base de datos
        
        Returns:
            Conexión SQLite
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            # Habilitar el modo de diccionario para row factory
            self.conn.row_factory = sqlite3.Row
        return self.conn
        
    def initialize_db(self):
        """
        Inicializa el esquema de la base de datos
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Crear tabla de issues
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            issue_id INTEGER PRIMARY KEY,
            number INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            state TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL,
            user_login TEXT NOT NULL,
            assignees TEXT,
            labels TEXT,
            milestone TEXT,
            comments_count INTEGER NOT NULL,
            reactions_total_count INTEGER NOT NULL,
            url TEXT NOT NULL,
            is_pull_request BOOLEAN NOT NULL
        )
        ''')
        
        # Crear tabla de comentarios
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY,
            issue_id INTEGER NOT NULL,
            user_login TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            body TEXT NOT NULL,
            reactions_total_count INTEGER NOT NULL,
            url TEXT NOT NULL,
            FOREIGN KEY (issue_id) REFERENCES issues(issue_id)
        )
        ''')
        
        # Crear índices para mejorar el rendimiento
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_issues_number ON issues(number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_issue_id ON comments(issue_id)')
        
        conn.commit()
        
    def save_issues(self, issues):
        """
        Guarda los issues en la base de datos
        
        Args:
            issues: Lista de issues en formato JSON
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for issue in issues:
            # Extraer los datos necesarios
            issue_id = issue['id']
            number = issue['number']
            title = issue['title']
            body = issue.get('body', '')
            state = issue['state']
            created_at = issue['created_at']
            closed_at = issue['closed_at']
            updated_at = issue['updated_at']
            user_login = issue['user']['login']
            
            # Procesar assignees
            assignees = []
            for assignee in issue.get('assignees', []):
                assignees.append(assignee['login'])
            assignees_str = ','.join(assignees)
            
            # Procesar labels
            labels = []
            for label in issue.get('labels', []):
                labels.append(label['name'])
            labels_str = ','.join(labels)
            
            # Milestone
            milestone = issue.get('milestone', {})
            milestone_str = milestone.get('title', '') if milestone else ''
            
            # Otros campos
            comments_count = issue['comments']
            reactions_total_count = issue.get('reactions', {}).get('total_count', 0)
            url = issue['html_url']
            
            # Verificar si es un pull request
            is_pull_request = 'pull_request' in issue
            
            # Insertar en la base de datos
            cursor.execute('''
            INSERT OR REPLACE INTO issues (
                issue_id, number, title, body, state, created_at, closed_at, updated_at,
                user_login, assignees, labels, milestone, comments_count,
                reactions_total_count, url, is_pull_request
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                issue_id, number, title, body, state, created_at, closed_at, updated_at,
                user_login, assignees_str, labels_str, milestone_str, comments_count,
                reactions_total_count, url, is_pull_request
            ))
        
        conn.commit()
        print(f"Guardados {len(issues)} issues en la base de datos")
        
    def save_comments(self, comments):
        """
        Guarda los comentarios en la base de datos
        
        Args:
            comments: Lista de comentarios en formato JSON
        """
        if not comments:
            return
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for comment in comments:
            # Extraer los datos necesarios
            comment_id = comment['id']
            issue_id = self._extract_issue_id_from_url(comment['issue_url'])
            user_login = comment['user']['login']
            created_at = comment['created_at']
            updated_at = comment['updated_at']
            body = comment['body']
            reactions_total_count = comment.get('reactions', {}).get('total_count', 0)
            url = comment['html_url']
            
            # Insertar en la base de datos
            cursor.execute('''
            INSERT OR REPLACE INTO comments (
                comment_id, issue_id, user_login, created_at, updated_at,
                body, reactions_total_count, url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                comment_id, issue_id, user_login, created_at, updated_at,
                body, reactions_total_count, url
            ))
        
        conn.commit()
        print(f"Guardados {len(comments)} comentarios en la base de datos")
        
    def _extract_issue_id_from_url(self, issue_url):
        """
        Extrae el ID del issue desde la URL
        
        Args:
            issue_url: URL del issue
            
        Returns:
            ID del issue
        """
        # Consultar la base de datos para obtener el issue_id basado en el número
        parts = issue_url.split('/')
        issue_number = int(parts[-1])
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT issue_id FROM issues WHERE number = ?', (issue_number,))
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Si no encontramos el issue, devolvemos None
            print(f"Advertencia: No se encontró el issue con número {issue_number}")
            return None
    
    def query_issues(self, state=None, labels=None, limit=100):
        """
        Consulta issues en la base de datos
        
        Args:
            state: Estado de los issues ('open', 'closed', None para todos)
            labels: Lista de etiquetas para filtrar
            limit: Número máximo de resultados
            
        Returns:
            Lista de issues
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM issues'
        params = []
        conditions = []
        
        if state:
            conditions.append('state = ?')
            params.append(state)
            
        if labels:
            # Buscamos issues que contengan al menos una etiqueta
            placeholders = []
            for label in labels:
                conditions.append('labels LIKE ?')
                params.append(f'%{label}%')
                
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
            
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def get_issue_with_comments(self, issue_number):
        """
        Obtiene un issue con todos sus comentarios
        
        Args:
            issue_number: Número del issue
            
        Returns:
            Tuple (issue, comments)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener el issue
        cursor.execute('SELECT * FROM issues WHERE number = ?', (issue_number,))
        issue = cursor.fetchone()
        
        if not issue:
            return None, []
            
        # Obtener los comentarios
        cursor.execute('SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at', (issue['issue_id'],))
        comments = cursor.fetchall()
        
        return issue, comments
    
    def close(self):
        """
        Cierra la conexión a la base de datos
        """
        if self.conn:
            self.conn.close()
            self.conn = None

def parse_args():
    parser = argparse.ArgumentParser(description='Extractor de issues y comentarios de GitHub')
    parser.add_argument('--owner', type=str, default='dotnet', help='Propietario del repositorio')
    parser.add_argument('--repo', type=str, default='efcore', help='Nombre del repositorio')
    parser.add_argument('--state', type=str, default='open', choices=['open', 'closed', 'all'], 
                        help='Estado de los issues a extraer')
    parser.add_argument('--max-issues', type=int, default=50, 
                        help='Número máximo de issues a extraer')
    parser.add_argument('--labels', type=str, nargs='+', 
                        help='Etiquetas para filtrar los issues (separadas por espacios)')
    parser.add_argument('--list-labels', action='store_true', 
                        help='Solo mostrar las etiquetas disponibles en el repositorio')
    parser.add_argument('--token', type=str, help='Token de GitHub para autenticación')
    parser.add_argument('--db-path', type=str, default='github_issues.db',
                       help='Ruta al archivo de base de datos SQLite (por defecto: github_issues.db)')
    parser.add_argument('--no-db', action='store_true',
                       help='No guardar en base de datos, solo archivos JSON')
    parser.add_argument('--query-db', action='store_true',
                       help='Consultar issues desde la base de datos en lugar de GitHub')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Usar token proporcionado como argumento o variable de entorno
    token = args.token or os.environ.get("GITHUB_TOKEN")
    
    # Configurar path de base de datos
    db_path = None if args.no_db else args.db_path
    
    # Inicializar el extractor para el repositorio
    extractor = GitHubIssueExtractor(args.owner, args.repo, token, db_path)
    
    # Si se solicitó consultar la base de datos
    if args.query_db and not args.no_db:
        db_manager = DatabaseManager(args.db_path)
        print(f"Consultando base de datos {args.db_path}")
        
        # Obtener issues según los filtros
        issues = db_manager.query_issues(state=args.state, labels=args.labels, limit=args.max_issues)
        
        print(f"\nSe encontraron {len(issues)} issues en la base de datos:")
        for issue in issues:
            print(f"#{issue['number']}: {issue['title']} - Estado: {issue['state']}")
            
            # Obtener los comentarios para este issue si hay
            if issue['comments_count'] > 0:
                _, comments = db_manager.get_issue_with_comments(issue['number'])
                print(f"  - {len(comments)} comentarios")
        
        db_manager.close()
        return
    
    # Si solo se quieren listar las etiquetas
    if args.list_labels:
        labels = extractor.get_repository_labels()
        print("\nEtiquetas disponibles en el repositorio:")
        for label in labels:
            print(f"- {label['name']}: {label['description'] or 'Sin descripción'}")
        return
    
    # Obtener issues con comentarios
    print(f"Extrayendo issues {args.state} del repositorio {args.owner}/{args.repo}")
    if args.labels:
        print(f"Filtrando por etiquetas: {', '.join(args.labels)}")
        
    issues, comments = extractor.get_all_issues_with_comments(
        state=args.state, 
        labels=args.labels, 
        max_issues=args.max_issues
    )
    
    # Mostrar estadísticas básicas
    print(f"\nSe han extraído {len(issues)} issues con un total de {sum(len(c) for c in comments.values())} comentarios")
    
    # Mostrar los 5 issues con más comentarios
    if issues:
        issue_comment_counts = [(issue["number"], len(comments[issue["number"]])) for issue in issues]
        top_issues = sorted(issue_comment_counts, key=lambda x: x[1], reverse=True)[:5]
        
        print("\nTop 5 issues por número de comentarios:")
        for issue_number, comment_count in top_issues:
            issue_title = next((i["title"] for i in issues if i["number"] == issue_number), "Desconocido")
            print(f"Issue #{issue_number}: {issue_title} - {comment_count} comentarios")
            
    # Cerrar la conexión a la base de datos si se ha utilizado
    if extractor.db_manager:
        extractor.db_manager.close()

if __name__ == "__main__":
    main()
