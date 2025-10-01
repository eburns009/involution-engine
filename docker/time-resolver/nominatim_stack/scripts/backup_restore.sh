#!/bin/bash
# Backup and Recovery Script
# ==========================
#
# Comprehensive backup and restore functionality for the entire system
# Supports incremental and full backups with verification

set -e

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_BASE_DIR="/backups"
BACKUP_DIR="$BACKUP_BASE_DIR/backup_$TIMESTAMP"
RESTORE_DIR=""

# Configuration
RETENTION_DAYS=30
MAX_BACKUPS=10
COMPRESS_BACKUPS=true

# Parse command line arguments
OPERATION=""
BACKUP_TYPE="full"  # full, incremental, config-only

usage() {
    echo "Usage: $0 <operation> [options]"
    echo ""
    echo "Operations:"
    echo "  backup [full|incremental|config-only]  - Create backup"
    echo "  restore <backup_path>                  - Restore from backup"
    echo "  list                                   - List available backups"
    echo "  verify <backup_path>                   - Verify backup integrity"
    echo "  cleanup                                - Clean old backups"
    echo ""
    echo "Examples:"
    echo "  $0 backup full"
    echo "  $0 restore /backups/backup_2025-09-27_06-45-00"
    echo "  $0 list"
    echo "  $0 verify /backups/backup_2025-09-27_06-45-00"
    echo "  $0 cleanup"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

OPERATION="$1"
if [ $# -gt 1 ]; then
    if [ "$OPERATION" = "backup" ]; then
        BACKUP_TYPE="$2"
    elif [ "$OPERATION" = "restore" ] || [ "$OPERATION" = "verify" ]; then
        RESTORE_DIR="$2"
    fi
fi

echo "[$TIMESTAMP] 🔄 Starting $OPERATION operation..."

# Function to create backup directory structure
prepare_backup_dir() {
    echo "[$TIMESTAMP] 📁 Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"/{data,config,logs,metadata}

    # Create backup metadata
    cat > "$BACKUP_DIR/metadata/backup_info.json" << EOF
{
  "timestamp": "$TIMESTAMP",
  "backup_type": "$BACKUP_TYPE",
  "system_info": {
    "hostname": "$(hostname)",
    "docker_version": "$(docker --version 2>/dev/null || echo 'N/A')",
    "docker_compose_version": "$(docker-compose --version 2>/dev/null || echo 'N/A')"
  }
}
EOF
}

# Function to backup database
backup_database() {
    echo "[$TIMESTAMP] 🗄️  Backing up PostgreSQL database..."

    if docker-compose ps nominatim | grep -q "Up"; then
        # Create database dump
        docker-compose exec -T nominatim pg_dump -U nominatim -d nominatim --clean --if-exists > "$BACKUP_DIR/data/nominatim_database.sql"

        # Check if dump was successful
        if [ -s "$BACKUP_DIR/data/nominatim_database.sql" ]; then
            local dump_size=$(stat -c%s "$BACKUP_DIR/data/nominatim_database.sql")
            echo "[$TIMESTAMP] ✅ Database backup completed: $(numfmt --to=iec $dump_size)B"

            # Compress database dump
            if [ "$COMPRESS_BACKUPS" = true ]; then
                gzip "$BACKUP_DIR/data/nominatim_database.sql"
                echo "[$TIMESTAMP] 📦 Database backup compressed"
            fi
        else
            echo "[$TIMESTAMP] ❌ Database backup failed - empty dump file"
            return 1
        fi
    else
        echo "[$TIMESTAMP] ⚠️  Nominatim container not running - skipping database backup"
        echo '{"error": "Container not running"}' > "$BACKUP_DIR/data/database_backup_skipped.json"
    fi
}

# Function to backup Docker volumes
backup_volumes() {
    echo "[$TIMESTAMP] 💾 Backing up Docker volumes..."

    # Backup PostgreSQL data
    echo "[$TIMESTAMP]   📊 Backing up PostgreSQL data volume..."
    if docker volume ls | grep -q "nominatim_stack_pgdata"; then
        docker run --rm -v nominatim_stack_pgdata:/source -v "$BACKUP_DIR":/backup alpine tar czf /backup/data/pgdata_volume.tar.gz -C /source .
        echo "[$TIMESTAMP] ✅ PostgreSQL data volume backed up"
    else
        echo "[$TIMESTAMP] ⚠️  PostgreSQL data volume not found"
    fi

    # Backup Nominatim data
    echo "[$TIMESTAMP]   📊 Backing up Nominatim data volume..."
    if docker volume ls | grep -q "nominatim_stack_data"; then
        docker run --rm -v nominatim_stack_data:/source -v "$BACKUP_DIR":/backup alpine tar czf /backup/data/nominatim_data_volume.tar.gz -C /source .
        echo "[$TIMESTAMP] ✅ Nominatim data volume backed up"
    else
        echo "[$TIMESTAMP] ⚠️  Nominatim data volume not found"
    fi
}

# Function to backup configuration files
backup_configuration() {
    echo "[$TIMESTAMP] ⚙️  Backing up configuration files..."

    # Backup docker-compose.yml and related files
    if [ -f "docker-compose.yml" ]; then
        cp docker-compose.yml "$BACKUP_DIR/config/"
        echo "[$TIMESTAMP] ✅ docker-compose.yml backed up"
    fi

    # Backup environment files
    if [ -f ".env" ]; then
        cp .env "$BACKUP_DIR/config/"
        echo "[$TIMESTAMP] ✅ .env file backed up"
    fi

    # Backup scripts directory
    if [ -d "scripts" ]; then
        cp -r scripts "$BACKUP_DIR/config/"
        echo "[$TIMESTAMP] ✅ Scripts directory backed up"
    fi

    # Backup gateway configuration
    if [ -d "gateway" ]; then
        cp -r gateway "$BACKUP_DIR/config/"
        echo "[$TIMESTAMP] ✅ Gateway configuration backed up"
    fi

    # Backup cron configuration
    if [ -d "cron.d" ]; then
        cp -r cron.d "$BACKUP_DIR/config/"
        echo "[$TIMESTAMP] ✅ Cron configuration backed up"
    fi
}

# Function to backup logs (selective)
backup_logs() {
    echo "[$TIMESTAMP] 📄 Backing up important logs..."

    # Create logs directory in backup
    mkdir -p "$BACKUP_DIR/logs"

    # Backup recent application logs
    if [ -d "logs" ]; then
        find logs -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/logs/" \;
        echo "[$TIMESTAMP] ✅ Recent application logs backed up"
    fi

    # Export recent Docker logs
    echo "[$TIMESTAMP] 🐳 Exporting recent Docker container logs..."
    for container in nominatim nominatim-updater; do
        if docker ps -a --format "{{.Names}}" | grep -q "^${container}$"; then
            docker logs --since="168h" "$container" > "$BACKUP_DIR/logs/${container}_recent.log" 2>&1 || true
            echo "[$TIMESTAMP]   ✅ $container logs exported"
        fi
    done
}

# Function to create backup manifest
create_backup_manifest() {
    echo "[$TIMESTAMP] 📋 Creating backup manifest..."

    local manifest_file="$BACKUP_DIR/metadata/manifest.json"

    # Calculate checksums for backup files
    echo "[$TIMESTAMP] 🔍 Calculating file checksums..."

    find "$BACKUP_DIR" -type f -not -path "*/metadata/*" -exec md5sum {} \; > "$BACKUP_DIR/metadata/checksums.md5"

    # Count files and calculate total size
    local file_count=$(find "$BACKUP_DIR" -type f -not -path "*/metadata/*" | wc -l)
    local total_size=$(du -sb "$BACKUP_DIR" | cut -f1)

    cat > "$manifest_file" << EOF
{
  "backup_info": {
    "timestamp": "$TIMESTAMP",
    "type": "$BACKUP_TYPE",
    "file_count": $file_count,
    "total_size_bytes": $total_size,
    "total_size_human": "$(numfmt --to=iec $total_size)B"
  },
  "components": {
    "database": $([ -f "$BACKUP_DIR/data/nominatim_database.sql" ] || [ -f "$BACKUP_DIR/data/nominatim_database.sql.gz" ] && echo "true" || echo "false"),
    "volumes": $([ -f "$BACKUP_DIR/data/pgdata_volume.tar.gz" ] && echo "true" || echo "false"),
    "configuration": $([ -f "$BACKUP_DIR/config/docker-compose.yml" ] && echo "true" || echo "false"),
    "logs": $([ -d "$BACKUP_DIR/logs" ] && echo "true" || echo "false")
  },
  "verification": {
    "checksum_file": "metadata/checksums.md5",
    "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }
}
EOF

    echo "[$TIMESTAMP] ✅ Backup manifest created"
}

# Function to perform full backup
perform_backup() {
    echo "[$TIMESTAMP] 📦 Starting $BACKUP_TYPE backup..."

    prepare_backup_dir

    case "$BACKUP_TYPE" in
        "full")
            backup_database
            backup_volumes
            backup_configuration
            backup_logs
            ;;
        "incremental")
            # For incremental, only backup changed configurations and recent logs
            backup_configuration
            backup_logs
            # TODO: Implement true incremental database backup
            echo "[$TIMESTAMP] ℹ️  Incremental database backup not yet implemented"
            ;;
        "config-only")
            backup_configuration
            ;;
        *)
            echo "[$TIMESTAMP] ❌ Unknown backup type: $BACKUP_TYPE"
            exit 1
            ;;
    esac

    create_backup_manifest

    # Create final backup archive (optional)
    if [ "$COMPRESS_BACKUPS" = true ] && [ "$BACKUP_TYPE" = "full" ]; then
        echo "[$TIMESTAMP] 📦 Creating compressed backup archive..."
        tar czf "${BACKUP_DIR}.tar.gz" -C "$BACKUP_BASE_DIR" "$(basename "$BACKUP_DIR")"

        if [ -f "${BACKUP_DIR}.tar.gz" ]; then
            local archive_size=$(stat -c%s "${BACKUP_DIR}.tar.gz")
            echo "[$TIMESTAMP] ✅ Backup archive created: $(numfmt --to=iec $archive_size)B"

            # Remove uncompressed backup directory
            rm -rf "$BACKUP_DIR"
            echo "[$TIMESTAMP] 🗑️  Uncompressed backup directory removed"
        fi
    fi

    echo "[$TIMESTAMP] ✅ Backup completed successfully!"
    echo "[$TIMESTAMP] 📁 Backup location: $([ -f "${BACKUP_DIR}.tar.gz" ] && echo "${BACKUP_DIR}.tar.gz" || echo "$BACKUP_DIR")"
}

# Function to list available backups
list_backups() {
    echo "[$TIMESTAMP] 📋 Available backups:"

    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        echo "[$TIMESTAMP] ℹ️  No backup directory found"
        return 0
    fi

    # List compressed backups
    find "$BACKUP_BASE_DIR" -name "backup_*.tar.gz" -type f | sort -r | while read -r backup; do
        local size=$(stat -c%s "$backup")
        local date=$(stat -c%y "$backup" | cut -d' ' -f1)
        echo "[$TIMESTAMP]   📦 $(basename "$backup") - $(numfmt --to=iec $size)B ($date)"
    done

    # List uncompressed backups
    find "$BACKUP_BASE_DIR" -name "backup_*" -type d | sort -r | while read -r backup; do
        local size=$(du -sb "$backup" | cut -f1)
        local date=$(stat -c%y "$backup" | cut -d' ' -f1)
        echo "[$TIMESTAMP]   📁 $(basename "$backup") - $(numfmt --to=iec $size)B ($date)"
    done
}

# Function to verify backup integrity
verify_backup() {
    local backup_path="$1"

    echo "[$TIMESTAMP] 🔍 Verifying backup: $backup_path"

    if [ ! -e "$backup_path" ]; then
        echo "[$TIMESTAMP] ❌ Backup not found: $backup_path"
        exit 1
    fi

    local temp_dir="/tmp/backup_verify_$$"
    mkdir -p "$temp_dir"

    # Extract if compressed
    if [[ "$backup_path" == *.tar.gz ]]; then
        echo "[$TIMESTAMP] 📦 Extracting compressed backup..."
        tar xzf "$backup_path" -C "$temp_dir"
        local extracted_dir=$(find "$temp_dir" -name "backup_*" -type d | head -1)
        backup_path="$extracted_dir"
    fi

    # Verify manifest exists
    if [ ! -f "$backup_path/metadata/manifest.json" ]; then
        echo "[$TIMESTAMP] ❌ Backup manifest not found"
        cleanup_temp_dir "$temp_dir"
        exit 1
    fi

    # Verify checksums
    if [ -f "$backup_path/metadata/checksums.md5" ]; then
        echo "[$TIMESTAMP] 🔍 Verifying file checksums..."
        cd "$backup_path"

        if md5sum -c metadata/checksums.md5 >/dev/null 2>&1; then
            echo "[$TIMESTAMP] ✅ All file checksums verified"
        else
            echo "[$TIMESTAMP] ❌ Checksum verification failed"
            cleanup_temp_dir "$temp_dir"
            exit 1
        fi
    fi

    # Check backup components
    local manifest="$backup_path/metadata/manifest.json"
    echo "[$TIMESTAMP] 📋 Backup verification summary:"

    if [ -f "$manifest" ]; then
        local file_count=$(grep '"file_count"' "$manifest" | grep -o '[0-9]*')
        local total_size=$(grep '"total_size_human"' "$manifest" | cut -d'"' -f4)
        echo "[$TIMESTAMP]   Files: $file_count"
        echo "[$TIMESTAMP]   Size: $total_size"

        # Check individual components
        if grep -q '"database": true' "$manifest"; then
            echo "[$TIMESTAMP]   ✅ Database backup present"
        fi

        if grep -q '"volumes": true' "$manifest"; then
            echo "[$TIMESTAMP]   ✅ Volume backup present"
        fi

        if grep -q '"configuration": true' "$manifest"; then
            echo "[$TIMESTAMP]   ✅ Configuration backup present"
        fi
    fi

    cleanup_temp_dir "$temp_dir"
    echo "[$TIMESTAMP] ✅ Backup verification completed successfully"
}

# Function to clean up old backups
cleanup_backups() {
    echo "[$TIMESTAMP] 🗑️  Cleaning up old backups..."

    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        echo "[$TIMESTAMP] ℹ️  No backup directory found"
        return 0
    fi

    # Remove backups older than retention period
    local deleted_count=0

    find "$BACKUP_BASE_DIR" -name "backup_*" -mtime +$RETENTION_DAYS | while read -r old_backup; do
        echo "[$TIMESTAMP]   🗑️  Removing old backup: $(basename "$old_backup")"
        rm -rf "$old_backup"
        deleted_count=$((deleted_count + 1))
    done

    # Keep only the most recent backups (regardless of age)
    local backup_list=$(find "$BACKUP_BASE_DIR" -name "backup_*" | sort -r)
    local backup_count=$(echo "$backup_list" | wc -l)

    if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
        echo "$backup_list" | tail -n +$((MAX_BACKUPS + 1)) | while read -r excess_backup; do
            echo "[$TIMESTAMP]   🗑️  Removing excess backup: $(basename "$excess_backup")"
            rm -rf "$excess_backup"
            deleted_count=$((deleted_count + 1))
        done
    fi

    echo "[$TIMESTAMP] ✅ Backup cleanup completed"
}

# Function to cleanup temporary directories
cleanup_temp_dir() {
    local temp_dir="$1"
    if [ -n "$temp_dir" ] && [ -d "$temp_dir" ]; then
        rm -rf "$temp_dir"
    fi
}

# Main execution
case "$OPERATION" in
    "backup")
        perform_backup
        ;;
    "restore")
        if [ -z "$RESTORE_DIR" ]; then
            echo "[$TIMESTAMP] ❌ Restore path required"
            usage
        fi
        echo "[$TIMESTAMP] ⚠️  Restore functionality not yet implemented"
        echo "[$TIMESTAMP] 💡 Use backup verification and manual restore for now"
        ;;
    "list")
        list_backups
        ;;
    "verify")
        if [ -z "$RESTORE_DIR" ]; then
            echo "[$TIMESTAMP] ❌ Backup path required for verification"
            usage
        fi
        verify_backup "$RESTORE_DIR"
        ;;
    "cleanup")
        cleanup_backups
        ;;
    *)
        echo "[$TIMESTAMP] ❌ Unknown operation: $OPERATION"
        usage
        ;;
esac

echo "[$TIMESTAMP] ✅ Operation completed successfully!"